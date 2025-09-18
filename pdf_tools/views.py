import os
import tempfile
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, FileResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import PyPDF4
from PyPDF4 import PdfFileWriter, PdfFileReader
from io import BytesIO
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import json
from pdf2docx import Converter
import pdfplumber
import pandas as pd

def home(request):
    return render(request, 'pdf_tools/home.html')

@csrf_exempt
@require_http_methods(["POST"])
def merge_pdfs(request):
    try:
        files = request.FILES.getlist('files')
        if len(files) < 2:
            return JsonResponse({'error': 'Se necesitan al menos 2 archivos PDF'}, status=400)
        
        merger = PdfFileWriter()
        
        for file in files:
            if not file.name.endswith('.pdf'):
                return JsonResponse({'error': 'Solo se permiten archivos PDF'}, status=400)
            
            # Leer el archivo directamente desde el request
            file.seek(0)  # Asegurar que estamos al inicio del archivo
            reader = PdfFileReader(file)
            for page in range(reader.getNumPages()):
                merger.addPage(reader.getPage(page))
        
        # Crear archivo de salida
        output_filename = 'merged_document.pdf'
        output_path = f'output/{output_filename}'
        
        buffer = BytesIO()
        merger.write(buffer)
        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))
        
        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def split_pdf(request):
    try:
        file = request.FILES.get('file')
        if not file or not file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Se requiere un archivo PDF válido'}, status=400)
        
        # Leer el archivo directamente desde el request
        file.seek(0)  # Asegurar que estamos al inicio del archivo
        reader = PdfFileReader(file)
        num_pages = reader.getNumPages()
        
        # Opcionales: rango de páginas y modo de salida
        page_range_str = request.POST.get('range', '').strip()
        merge_pages = request.POST.get('merge_pages', 'false').lower() == 'true'

        # Función auxiliar para parsear rangos: "1-3,5,7-9"
        def parse_page_range(range_str: str, total_pages: int):
            if not range_str:
                return list(range(total_pages))
            selected = []
            parts = [p.strip() for p in range_str.split(',') if p.strip()]
            for part in parts:
                if '-' in part:
                    start_str, end_str = part.split('-', 1)
                    try:
                        start = max(1, int(start_str))
                        end = min(total_pages, int(end_str))
                        if start <= end:
                            selected.extend(list(range(start - 1, end)))  # a índice base 0
                    except ValueError:
                        continue
                else:
                    try:
                        page_one_based = int(part)
                        if 1 <= page_one_based <= total_pages:
                            selected.append(page_one_based - 1)
                    except ValueError:
                        continue
            # Eliminar duplicados preservando orden
            seen = set()
            ordered_unique = []
            for idx in selected:
                if idx not in seen:
                    seen.add(idx)
                    ordered_unique.append(idx)
            return ordered_unique or list(range(total_pages))

        selected_indices = parse_page_range(page_range_str, num_pages)

        if merge_pages:
            # Extraer el rango seleccionado en un solo PDF
            writer = PdfFileWriter()
            for page_idx in selected_indices:
                writer.addPage(reader.getPage(page_idx))
            output_filename = 'extracted_pages.pdf' if page_range_str else 'extracted_all_pages.pdf'
            output_path = f'output/{output_filename}'
            buffer = BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            default_storage.save(output_path, ContentFile(buffer.getvalue()))
            return JsonResponse({
                'success': True,
                'download_url': f'/download/{output_filename}/',
                'filename': output_filename,
                'total_pages': num_pages,
                'selected_pages': [i + 1 for i in selected_indices]
            })
        else:
            # Dividir en archivos por página (todas o sólo el rango)
            output_files = []
            for page_idx in selected_indices:
                writer = PdfFileWriter()
                writer.addPage(reader.getPage(page_idx))
                output_filename = f'page_{page_idx + 1}.pdf'
                output_path = f'output/{output_filename}'
                buffer = BytesIO()
                writer.write(buffer)
                buffer.seek(0)
                default_storage.save(output_path, ContentFile(buffer.getvalue()))
                output_files.append({
                    'filename': output_filename,
                    'download_url': f'/download/{output_filename}/',
                    'page': page_idx + 1
                })
            return JsonResponse({
                'success': True,
                'files': output_files,
                'total_pages': num_pages,
                'selected_pages': [i + 1 for i in selected_indices]
            })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def compress_pdf(request):
    try:
        file = request.FILES.get('file')
        if not file or not file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Se requiere un archivo PDF válido'}, status=400)
        
        # Leer el archivo directamente desde el request
        file.seek(0)  # Asegurar que estamos al inicio del archivo
        reader = PdfFileReader(file)
        writer = PdfFileWriter()
        
        for page_num in range(reader.getNumPages()):
            page = reader.getPage(page_num)
            # Comprimir eliminando objetos duplicados
            page.compressContentStreams()
            writer.addPage(page)
        
        output_filename = f'compressed_{file.name}'
        output_path = f'output/{output_filename}'
        
        buffer = BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))
        
        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def images_to_pdf(request):
    try:
        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'error': 'Se requieren archivos de imagen'}, status=400)
        
        # Crear PDF con reportlab usando BytesIO
        output_filename = 'images_to_pdf.pdf'
        output_path = f'output/{output_filename}'
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        temp_files = []  # Para limpiar archivos temporales después
        
        for file in files:
            if not file.content_type.startswith('image/'):
                continue
            
            # Leer la imagen directamente desde el request
            file.seek(0)  # Asegurar que estamos al inicio del archivo
            img = Image.open(file)
            img_width, img_height = img.size
            
            # Calcular dimensiones manteniendo proporción
            ratio = min(width / img_width, height / img_height)
            new_width = img_width * ratio
            new_height = img_height * ratio
            
            x = (width - new_width) / 2
            y = (height - new_height) / 2
            
            # Convertir imagen a formato compatible con reportlab
            # Convertir a RGB si es necesario (para PNG con transparencia)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Crear archivo temporal para reportlab
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_files.append(temp_file.name)
            img.save(temp_file.name, format='JPEG', quality=95)
            temp_file.close()
            
            # Crear nueva página y añadir imagen
            c.drawImage(temp_file.name, x, y, new_width, new_height)
            c.showPage()
        
        c.save()
        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))
        
        # Limpiar archivos temporales
        for temp_file_path in temp_files:
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })
    
    except Exception as e:
        # Limpiar archivos temporales en caso de error
        for temp_file_path in temp_files:
            try:
                os.unlink(temp_file_path)
            except:
                pass
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def rotate_pdf(request):
    try:
        file = request.FILES.get('file')
        rotation = int(request.POST.get('rotation', 90))
        
        if not file or not file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Se requiere un archivo PDF válido'}, status=400)
        
        if rotation not in [90, 180, 270]:
            return JsonResponse({'error': 'La rotación debe ser 90, 180 o 270 grados'}, status=400)
        
        # Leer el archivo directamente desde el request
        file.seek(0)  # Asegurar que estamos al inicio del archivo
        reader = PdfFileReader(file)
        writer = PdfFileWriter()
        
        for page_num in range(reader.getNumPages()):
            page = reader.getPage(page_num)
            page.rotateClockwise(rotation)
            writer.addPage(page)
        
        output_filename = f'rotated_{rotation}_{file.name}'
        output_path = f'output/{output_filename}'
        
        buffer = BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))
        
        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def download_file(request, filename):
    try:
        file_path = f'output/{filename}'
        if default_storage.exists(file_path):
            response = FileResponse(
                default_storage.open(file_path, 'rb'),
                as_attachment=True,
                filename=filename
            )
            return response
        else:
            return HttpResponse('Archivo no encontrado', status=404)
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

@csrf_exempt
@require_http_methods(["POST"])
def pdf_to_word(request):
    try:
        file = request.FILES.get('file')

        if not file or not file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Se requiere un archivo PDF válido'}, status=400)

        # Guardar PDF temporalmente
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        for chunk in file.chunks():
            temp_pdf.write(chunk)
        temp_pdf.close()

        # Convertir PDF a DOCX en memoria
        output_filename = file.name.replace('.pdf', '.docx')
        output_path = f'output/{output_filename}'

        buffer = BytesIO()
        cv = Converter(temp_pdf.name)
        cv.convert(buffer, start=0, end=None)
        cv.close()

        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))

        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
@require_http_methods(["POST"])
def pdf_to_excel(request):
    try:
        file = request.FILES.get('file')

        if not file or not file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Se requiere un archivo PDF válido'}, status=400)

        # Guardar PDF temporalmente
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        for chunk in file.chunks():
            temp_pdf.write(chunk)
        temp_pdf.close()

        # Extraer tablas
        all_tables = []
        with pdfplumber.open(temp_pdf.name) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    df = pd.DataFrame(table)
                    all_tables.append(df)

        if not all_tables:
            return JsonResponse({'error': 'No se encontraron tablas en el PDF'}, status=400)

        # Consolidar en un solo Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for i, df in enumerate(all_tables, start=1):
                df.to_excel(writer, index=False, header=False, sheet_name=f"Tabla_{i}")

        # Guardar en output/
        output_filename = file.name.replace('.pdf', '.xlsx')
        output_path = f'output/{output_filename}'

        buffer.seek(0)
        default_storage.save(output_path, ContentFile(buffer.getvalue()))

        return JsonResponse({
            'success': True,
            'download_url': f'/download/{output_filename}/',
            'filename': output_filename
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)