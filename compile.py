import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from tqdm import tqdm
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader, select_autoescape

def mock_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename') or values.get('path', '')
        return f"static/{filename}".replace('//', '/')
    
    query_params = "&".join(f"{k}={v}" for k, v in values.items())
    return f"/{endpoint}?{query_params}" if query_params else f"/{endpoint}"

def select_paths():
    root = tk.Tk()
    root.withdraw()

    file_paths = filedialog.askopenfilenames(
        title="Select Jinja2 HTML Files to Compile",
        filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
    )
    if not file_paths:
        return None, None

    output_dir = filedialog.askdirectory(
        title="Select Output Directory for Compiled HTML"
    )
    if not output_dir:
        return None, None

    return [Path(f) for f in file_paths], Path(output_dir)

def compile_selected_files(file_paths, output_path, context_data):
    output_path.mkdir(parents=True, exist_ok=True)

    template_dirs = list(set(str(f.parent) for f in file_paths))
    
    env = SandboxedEnvironment(
        loader=FileSystemLoader(template_dirs),
        autoescape=select_autoescape(['html', 'xml', 'xhtml'])
    )

    env.globals['url_for'] = mock_url_for

    for file_path in tqdm(file_paths, desc="Processing Templates", unit="file"):
        try:
            template = env.get_template(file_path.name)
            rendered_content = template.render(context_data)
            
            output_file = output_path / file_path.name
            output_file.write_text(rendered_content, encoding='utf-8')
            
        except Exception as e:
            print(f"\nError compiling {file_path.name}: {e}")

if __name__ == "__main__":
    global_context = {
        "site_title": "Secure Platform",
        "user_role": "Administrator"
    }
    
    files, output = select_paths()
    if files and output:
        compile_selected_files(files, output, global_context)
