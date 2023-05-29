import glob
import os
import re
import subprocess

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from .models import File
from django.shortcuts import get_object_or_404
from .forms import DirectoryForm
from .models import Directory
from .forms import FileForm
from django.http import HttpRequest
from flask import Flask
from .forms import NewUserForm
from django.contrib import messages
from django.core import serializers


patterns = [
    r"/\*[\s\S]*?\*/", 
    r"//.*",  
    r"#\s*(include|define|ifdef|ifndef|endif|if|else|elif)\b",
    r"\b(const|char|short|int|long|float|double|void)\b",
]


def is_dir(path):
    return os.path.isdir(path)

# def delete_directory(request, directory_id):
#     directory = get_object_or_404(Directory, id=directory_id)
#     directory.is_deleted = True
#     directory.save()
#     return redirect("index")


# def delete_document(request, document_id):
#     document = get_object_or_404(File, id=document_id)
#     document.is_deleted = True
#     document.save()
    
#     directories = Directory.objects.filter(is_deleted=False)
#     documents = File.objects.filter(is_deleted=False)
#     documents_and_directories = list(documents) + list(directories)
#     document_list = []

#     for document in documents_and_directories:
#         if isinstance(document, File):
#             document_dict = {
#                 'id': document.id,
#                 'name': document.file.name,
#                 'type': 'file',
#                 'is_deleted': document.is_deleted,
#             }
#         elif isinstance(document, Directory):
#             document_dict = {
#                 'id': document.id,
#                 'name': document.name,
#                 'type': 'directory',
#                 'is_deleted': document.is_deleted,
#             }
        
#         document_list.append(document_dict)

#     return JsonResponse({"documents": document_list})



def get_documents_and_directories(request):
    directories = Directory.objects.filter(is_deleted=False)
    documents = File.objects.filter(is_deleted=False)
    documents_and_directories = list(documents) + list(directories)
    serialized_data = serializers.serialize('json', documents_and_directories)
    return JsonResponse({"documents_and_directories": serialized_data})

def upload_file(request):
    if request.method == 'POST':
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.save()
            directories = Directory.objects.filter(is_deleted=False)
            documents = File.objects.filter(is_deleted=False)
            documents_and_directories = list(documents) + list(directories)
            serialized_data = serializers.serialize('json', documents_and_directories)
            return JsonResponse({ 
                "link": file.file.url,
                "documents_and_directories": serialized_data
            })

 
def add_directory(request):
    if request.method == "POST":
        form = DirectoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            parent_folder = form.cleaned_data["parent_folder"]
            if parent_folder:
                parent_folder_path = os.path.join(
                    settings.MEDIA_ROOT, parent_folder.name
                )
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
            return redirect("index")
    else:
        form = DirectoryForm()
    return render(request, "add_directory.html", {"form": form})


def index2(request):
    directories = Directory.objects.filter(is_deleted=False)
    documents = File.objects.filter(is_deleted=False)
    documents_and_directories = list(documents) + list(directories)

    if not request.user.is_authenticated:
        return redirect("/accounts/login")

    if request.method == "POST":
        processor = request.POST.get("processor", "")
        optimization = request.POST.get("optimization", "")
        standard = request.POST.get("standard", "")
        dependent1 = request.POST.get("dependent1", "")
        dependent2 = request.POST.get("dependent2", "")
        dependent3 = request.POST.get("dependent3", "")

        request.session["processor"] = processor
        request.session["optimization"] = optimization
        request.session["standard"] = standard
        request.session["dependent1"] = dependent1
        request.session["dependent2"] = dependent2
        request.session["dependent3"] = dependent3

    for item in documents_and_directories:
        if isinstance(item, File):
            print(item.file.name)
        elif isinstance(item, Directory):
            print(item.name)

    return render(
        request,
        "index.html",
        {
            "documents_and_directories": documents_and_directories,
        },
    )

def show_files(request):
    directories = Directory.objects.filter(is_deleted=False)
    documents = File.objects.filter(is_deleted=False)
    documents_and_directories = list(documents) + list(directories)

    if not request.user.is_authenticated:
        return redirect("/accounts/login")

    if request.method == "POST":
        processor = request.POST.get("processor", "")
        optimization = request.POST.get("optimization", "")
        standard = request.POST.get("standard", "")
        dependent1 = request.POST.get("dependent1", "")
        dependent2 = request.POST.get("dependent2", "")
        dependent3 = request.POST.get("dependent3", "")

        request.session["processor"] = processor
        request.session["optimization"] = optimization
        request.session["standard"] = standard
        request.session["dependent1"] = dependent1
        request.session["dependent2"] = dependent2
        request.session["dependent3"] = dependent3

    for item in documents_and_directories:
        if isinstance(item, File):
            print(item.file.name)
        elif isinstance(item, Directory):
            print(item.name)

    return render(
        request,
        "files.html",
        {
            "documents_and_directories": documents_and_directories,
        },
    )

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
    root_dir = settings.MEDIA_ROOT
    folder_list = []

    for root, dirs, files in os.walk(root_dir):
        rel_path = os.path.relpath(root, root_dir)
        folder_names = rel_path.split(os.path.sep)
        parent = None
        for folder_name in folder_names:
            try:
                folder = next(
                    item
                    for item in folder_list
                    if item["name"] == folder_name and item["parent"] == parent
                )
            except StopIteration:
                folder = {"name": folder_name,
                          "parent": parent, "children": []}
                folder_list.append(folder)
            parent = folder

        for file_name in files:
            folder["children"].append({"name": file_name})

    return render(request, "index.html", {"folder_list": folder_list})


def compile_file(request):
    files = glob.glob(os.path.join(settings.MEDIA_ROOT, "*.hex"))
    if files:
        os.remove(files[0])

    processor = request.POST.get("processor")
    optimization = request.POST.get("optimization")
    standard = request.POST.get("standard")
    dependent1 = request.POST.get("dependent1")
    dependent2 = request.POST.get("dependent2")
    dependent3 = request.POST.get("dependent3")

    compiler_options = ""
    if processor == "MCS51":
        compiler_options = "-mmcs51"
        if dependent2 == "small":
            compiler_options += " --model-small"
        elif dependent2 == "medium":
            compiler_options += " --model-medium"
        elif dependent2 == "large":
            compiler_options += " --model-large"
        elif dependent2 == "huge":
            compiler_options += " --model-huge"
    elif processor == "Z80":
        compiler_options = "-mz80"
        if dependent1 == "small":
            compiler_options += " --opt-code-speed"
        elif dependent1 == "medium":
            compiler_options += " --opt-code-speed --opt-code-size"
        elif dependent1 == "large":
            compiler_options += (
                " --opt-code-speed --opt-code-size --opt-alloc-model=large"
            )
    elif processor == "STM8":
        compiler_options = "-mstm8"
        if optimization == "size":
            compiler_options += " --opt-code-size"
        if dependent3 == "no_peep":
            compiler_options += " --no-peep"
        elif dependent3 == "fomit_frame_pointer":
            compiler_options += " --fomit-frame-pointer"
        elif dependent3 == "inline_functions":
            compiler_options += " --inline-functions"

    if optimization == "fast":
        compiler_options += " -mcode-size"
    elif optimization == "debug":
        compiler_options += " --debug"

    if standard == "c89":
        compiler_options += " --std-c89"
    elif standard == "c99":
        compiler_options += " --std-c99"
    elif standard == "c11":
        compiler_options += " --std-c11"

    file_id = request.session.get("file_id")
    asm_code, error_msg = process_file(file_id, compiler_options)

    if "warning" in request.session:
        if request.session["warning"]:
            del request.session["warning"]
    request.session["asm_file_content"] = asm_code

    if error_msg:
        request.session["warning"] = (
            "Wystąpił błąd podczas kompilacji.\n\n" + error_msg
        )

    response_data = {
        "asm_code":  asm_code,
        "warning": request.session.get("warning",  ""),
    }
    
    return JsonResponse(response_data)


def get_file_name_by_id(file_id):
    file = get_object_or_404(File, id=file_id)
    return file.file.name


def process_file(file_id, compiler_options):
    filename = get_file_name_by_id(file_id)
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    compiler_options_list = compiler_options.split()
    compiler_options_list.append("-S")
    compiler_options_list.append(filepath)
    result = subprocess.run(
        ["sdcc"] + compiler_options_list, capture_output=True, text=True
    )

    if result.returncode == 0:
        compiled_file_path = os.path.join(
            settings.MEDIA_ROOT, os.path.splitext(filename)[0] + ".hex"
        )

        asm_file = os.path.splitext(filename)[0] + ".asm"
        compiled_file = os.path.splitext(filename)[0] + ".hex"
        os.rename(asm_file, compiled_file_path)

        with open(compiled_file_path, "r") as f:
            compiled_code = f.read()
        return compiled_code, None
    else:
        error_msg = result.stderr.strip()
        return None, error_msg


def my_view(request: HttpRequest):
    file_id = request.GET.get("file_id")
    return render(request, "index.html", {"file_id": file_id})


app = Flask(__name__)


@app.route("/download_asm", methods=["GET"])
def download_asm(request):
    asm_content = request.GET.get("asm_content", "")
    file_content = asm_content
    response = HttpResponse(file_content, content_type="text/plain")
    response["Content-Disposition"] = 'attachment; filename="example.txt"'
    return response

def login(request):
    return render(request, "registration/login.html")


def register_request(request):
	if request.method == "POST":
		form = NewUserForm(request.POST)
		if form.is_valid():
			messages.success(request, "Registration successful." )
			return redirect("index")
		messages.error(request, "Unsuccessful registration. Invalid information.")
	form = NewUserForm()
	return render (request=request, template_name="registration/registration.html", context={"register_form":form})



def show_file_content(request, file_id):
    request.session['file_id'] = file_id
    sections_with_index = None
    file = get_object_or_404(File, pk=file_id)
    

    sections = split_file_by_patterns(
        os.path.join(settings.MEDIA_ROOT, str(file.file)), patterns
    )
    sections_with_index = [(i, section)
                        for i, section in enumerate(sections)]
    response_data = {
        "sections_with_index":sections_with_index, 
    }
            
    return JsonResponse(response_data)

def delete_document(request, document_id):
    document = get_object_or_404(File, id=document_id)
    document.is_deleted = True
    document.save()
    return redirect("index")

def delete_directory(request, directory_id):
    directory = get_object_or_404(Directory, id=directory_id)
    directory.is_deleted = True
    directory.save()
    return redirect("index")
