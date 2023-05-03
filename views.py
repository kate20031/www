import os
import re
import subprocess

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.conf import settings
from .models import File
from django.shortcuts import get_object_or_404
from .forms import DirectoryForm
from django.views.generic.edit import CreateView
from .models import Directory
from .forms import FileForm
from django.http import HttpRequest

patterns = [
    r'/\*[\s\S]*?\*/',  # Komentarze wielolinijkowe
    r'//.*',  # Komentarze jednolinijkowe
    r'#\s*(include|define|ifdef|ifndef|endif|if|else|elif|undef|pragma)\b',  # Dyrektywy preprocesora
    r'\b(const|char|short|int|long|float|double|void|struct|static|auto|volatile|signed|unsigned)\b',  # Słowa kluczowe
    # r'\b([_a-zA-Z][_a-zA-Z0-9]*)\(',  # Nazwy funkcji
    # r'(\'{1}[^\']*\'{1})|(\"{1}[^\"]*\"{1})',  # Łańcuchy znakowe
    # r'\b[0-9]*\.{0,1}[0-9]+\b',  # Stałe liczbowe
    # r'(\+\+|--|\+=|-=|\*=|/=|%=|==|!=|<=|>=|<|>|&&|\|\||&|\||\^|\~|\!|\?|:|<<|>>|<<=|>>=)',  # Operatory
    # r'[_a-zA-Z][_a-zA-Z0-9]*',  # Nazwy zmiennych
    # r'[\{\}\[\]\(\)]',  # Nawiasy
    # r'[,;.]',  # Znaki przestankowe
    # r'\s+'  # Białe znaki
]

def is_dir(path):
    return os.path.isdir(path)


def show_files(request):
    media_root = settings.MEDIA_ROOT
    files = []
    for root, dirs, filenames in os.walk(media_root):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    for directory in dirs:
        files.append(os.path.join(root, directory))
    context = {'files': files}
    return render(request, 'index.html', context)

def delete_directory(request, directory_id):
    directory = get_object_or_404(Directory, id=directory_id)
    directory.is_deleted = True
    directory.save()
    return redirect('index')

def delete_document(request, document_id):
    document = get_object_or_404(File, id=document_id)
    document.is_deleted = True
    document.save()
    return redirect('index')

def choose_file(request):
    if request.method == 'POST':
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            file = File(file=request.FILES['file'])
            file.save()
            uploaded_file_path = file.file.name
            sections = split_file_by_patterns("media/" + uploaded_file_path, patterns)
            return redirect('/index2?sections={}'.format("&".join(sections)))
    else:
        form = FileForm()
    return render(request, 'choose_file.html', {
        'form': form
    })

def add_directory(request):
    if request.method == 'POST':
        form = DirectoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            parent_folder = form.cleaned_data['parent_folder']
            if parent_folder:
                parent_folder_path = os.path.join(settings.MEDIA_ROOT, parent_folder.name)
                if not os.path.exists(parent_folder_path):
                    os.makedirs(parent_folder_path)
                new_folder_path = os.path.join(parent_folder_path, name)
            else:
                new_folder_path = os.path.join(settings.MEDIA_ROOT, name)
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            folder = form.save(commit=False)
            folder.path = new_folder_path
            folder.save()
            return redirect('index')
    else:
        form = DirectoryForm()
    return render(request, 'add_directory.html', {'form': form})

def index2(request):
    directories = Directory.objects.filter(is_deleted=False)
    documents = File.objects.filter(is_deleted=False)
    contents = None
    sections_with_index = None

    # Create a list that contains both the directories and the documents
    documents_and_directories = list(documents) + list(directories)

    if 'file_id' in request.GET:
        file_id = request.GET['file_id']
        file = get_object_or_404(File, pk=file_id)
        contents = file.file.read().decode()
        sections = split_file_by_patterns(os.path.join(settings.MEDIA_ROOT, str(file.file)), patterns)
        sections_with_index = [(i, section) for i, section in enumerate(sections)]

    return render(request, 'index.html', {'documents_and_directories': documents_and_directories, 'contents': contents, 'sections_with_index': sections_with_index})


def split_file_by_patterns(file_path, patterns):
    sections = []
    current_section = ""
    with open(file_path) as f:
        for line in f:
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    if current_section:
                        sections.append(current_section.strip())
                    current_section = line.strip()
                    break
            else:
                current_section += line

        if current_section:
            sections.append(current_section.strip())

    return sections


def folder_structure(request):
    """
    View to display folder structure.
    """
    root_dir = settings.MEDIA_ROOT
    folder_list = []

    for root, dirs, files in os.walk(root_dir):
        # Get relative path
        rel_path = os.path.relpath(root, root_dir)

        # Split path into list of folder names
        folder_names = rel_path.split(os.path.sep)

        # Add each folder to folder_list if it's not already there
        parent = None
        for folder_name in folder_names:
            try:
                folder = next(item for item in folder_list if item['name'] == folder_name and item['parent'] == parent)
            except StopIteration:
                folder = {'name': folder_name, 'parent': parent, 'children': []}
                folder_list.append(folder)
            parent = folder

        # Add files to current folder
        for file_name in files:
            folder['children'].append({'name': file_name})

    return render(request, 'index.html', {'folder_list': folder_list})

def compile_file(request):
    if request.method == 'POST':
        file_id = request.POST.get('file_id')  # pobierz id wybranego pliku

        # przetwórz i skompiluj plik
        result = process_file(file_id)

        if result.status_code == 200:
            asm_file_content = result.content.decode()  # pobierz zawartość pliku asemblerowego z odpowiedzi HTTP
            return render(request, 'index.html', {'asm_file_content': asm_file_content})  # przekaż zawartość pliku asemblerowego do kontekstu
        else:
            return HttpResponse('Wystąpił błąd podczas kompilacji pliku.')
    else:
        return render(request, 'index.html')
    
def get_file_name_by_id(file_id):
    file = get_object_or_404(File, id=file_id)
    return file.file.name
    
def get_file_name_by_id(file_id):
    file = get_object_or_404(File, id=file_id)
    return file.file.name

def process_file(file_id):
    try:
        filename = get_file_name_by_id(file_id)
        filepath = get_object_or_404(File, id=file_id).file.path
        with open(filepath, 'r') as f:
            c_file = f.read()
        print("here" + filename + c_file)
        file_obj = File.objects.get(id=file_id)

        result = subprocess.run(['sdcc', '-S', filepath], capture_output=True)
        print("Return code:", result.returncode)

        # Sprawdzanie, czy proces zakończył się poprawnie
        if result.returncode == 0:
            asm_file = filename.replace('.c', '.asm')
            with open(asm_file, 'r') as f:
                asm_code = f.read()
            return HttpResponse(asm_code, status=200)
        else:
            # W przypadku błędu zwróć kod błędu i wyjście procesu
            return HttpResponseServerError('Wystąpił błąd podczas kompilacji pliku.')
    except FileNotFoundError:
        return HttpResponseBadRequest('Nie znaleziono pliku o podanym ID.')

    
def my_view(request: HttpRequest):
    file_id = request.GET.get('file_id')
    return render(request, 'index.html', {'file_id': file_id})