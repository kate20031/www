import glob
import os
import re
import subprocess
from django.template.loader import render_to_string

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
from django.contrib.auth.models import User
from .forms import NewUserForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.files.storage import default_storage


patterns = [
    r"/\*[\s\S]*?\*/",  # Komentarze wielolinijkowe
    r"//.*",  # Komentarze jednolinijkowe
    # Dyrektywy preprocesora
    r"#\s*(include|define|ifdef|ifndef|endif|if|else|elif|undef|pragma)\b",
    # Słowa kluczowe
    r"\b(const|char|short|int|long|float|double|void|struct|static|auto|volatile|signed|unsigned)\b",
]


def is_dir(path):
    return os.path.isdir(path)


def show_files(request):
    media_root = settings.MEDIA_ROOT
    print("HEREEEEEE" + media_root)
    files = []
    for root, dirs, filenames in os.walk(media_root):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    for directory in dirs:
        files.append(os.path.join(root, directory))
    context = {"files": files}
    return render(request, "index.html", context)


def delete_directory(request, directory_id):
    directory = get_object_or_404(Directory, id=directory_id)
    directory.is_deleted = True
    directory.save()
    return redirect("index")


def delete_document(request, document_id):
    document = get_object_or_404(File, id=document_id)
    document.is_deleted = True
    document.save()
    return redirect("index")

def choose_file(request):
    if request.method == "POST":
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            file = File(file=request.FILES["file"])
            file.save()
            uploaded_file_path = file.file.name
            sections = split_file_by_patterns(
                "media/" + uploaded_file_path, patterns)
            return redirect("/index2?sections={}".format("&".join(sections)))
    else:
        form = FileForm()
    return render(request, "choose_file.html", {"form": form})

# def choose_file(request):
#     if request.method == "POST":
#         form = FileForm(request.POST, request.FILES)
#         if form.is_valid():
#             file = File(file=request.FILES["file"])
#             file.save()
#             uploaded_file_path = file.file.name
#             sections = split_file_by_patterns("media/" + uploaded_file_path, patterns)
#             return JsonResponse({"status": "success", "sections": sections})
#         else:
#             return JsonResponse({"status": "error", "message": form.errors})
#     else:
#         form = FileForm()
#     return render(request, "choose_file.html", {"form": form})



# #     return HttpResponse('Failed')
# from django.shortcuts import render
# from django.http import JsonResponse
# from django.views.decorators.csrf import ensure_csrf_cookie
 
# @ensure_csrf_cookie
# def upload_files(request):
#     if request.method == "GET":
#         return render(request, 'index.html', )
#     if request.method == 'POST':
#         files = request.FILES.getlist('files[]', None)
#         for f in files:
#             handle_uploaded_file(f)
#         return JsonResponse({'msg':'<div class="alert alert-success" role="alert">File successfully uploaded</div>'})
#     else:
#         return render(request, 'index.html', )
             
# def handle_uploaded_file(f):  
#     media_dir = os.path.join(settings.BASE_DIR, 'media')
#     file_path = os.path.join(media_dir, f.name)
#     with open(file_path, 'wb+') as destination:
#         for chunk in f.chunks():
#             destination.write(chunk)

def add_directory(request):
    if request.method == "POST":
        form = DirectoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            parent_folder = form.cleaned_data["parent_folder"]
            if parent_folder:
                # parent_folder_object = Directory.objects.filter(is_deleted=False, name = parent_folder)
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
    contents = None
    sections_with_index = None
    asm_file_content = request.session.get("asm_file_content", None)
    warning = request.session.get("warning", None)
    documents_and_directories = list(documents) + list(directories)

    if not request.user.is_authenticated:
        return redirect("/accounts/login")

    if "file_id" in request.GET:
        file_id = request.GET["file_id"]
        file = get_object_or_404(File, pk=file_id)
        contents = file.file.read().decode()
        sections = split_file_by_patterns(
            os.path.join(settings.MEDIA_ROOT, str(file.file)), patterns
        )
        sections_with_index = [(i, section)
                               for i, section in enumerate(sections)]

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

    return render(
        request,
        "index.html",
        {
            "documents_and_directories": documents_and_directories,
            "warning": warning,
            "contents": contents,
            "sections_with_index": sections_with_index,
            "asm_file_content": asm_file_content,
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
    if request.method == "POST":

        files = glob.glob(os.path.join(settings.MEDIA_ROOT, "*.hex"))
        if files:
            os.remove(files[0])

        file_id = request.POST.get("file_id")
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

    file_id = request.POST.get("file_id")
    asm_code, error_msg = process_file(file_id, compiler_options)

    if "warning" in request.session:
        if request.session["warning"]:
            del request.session["warning"]
    request.session["asm_file_content"] = asm_code

    if error_msg:
        request.session["warning"] = (
            "Wystąpił błąd podczas kompilacji pliku.\n\n" + error_msg
        )

    return redirect(request.META.get("HTTP_REFERER"))


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