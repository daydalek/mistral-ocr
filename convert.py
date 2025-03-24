from mistralai import Mistral
from pathlib import Path
import os
import base64
from mistralai import DocumentURLChunk
from mistralai.models import OCRResponse
import PyPDF2
import tempfile
import shutil
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import json
import threading
import subprocess

# 导入国际化支持模块
import i18n
from i18n import _

# 尝试导入tkinterdnd2用于拖放功能
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    for img_name, img_path in images_dict.items():
        markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({img_path})")
    return markdown_str

def save_ocr_results(ocr_response: OCRResponse, output_dir: str, page_offset: int = 0) -> None:
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    all_markdowns = []
    for i, page in enumerate(ocr_response.pages):
        # Save images
        page_images = {}
        for img in page.images:
            # Create a unique ID for images to avoid conflicts when merging
            unique_img_id = f"part{page_offset}_page{i}_{img.id}"
            img_data = base64.b64decode(img.image_base64.split(',')[1])
            img_path = os.path.join(images_dir, f"{unique_img_id}.png")
            with open(img_path, 'wb') as f:
                f.write(img_data)
            page_images[img.id] = f"images/{unique_img_id}.png"
        
        # Process markdown content
        page_markdown = replace_images_in_markdown(page.markdown, page_images)
        
        # Add page number information
        actual_page_num = page_offset + i + 1
        page_markdown = f"## 第 {actual_page_num} 页\n\n{page_markdown}"
        
        all_markdowns.append(page_markdown)
    
    # Save partial results
    partial_md_path = os.path.join(output_dir, f"part_{page_offset}.md")
    with open(partial_md_path, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(all_markdowns))
    
    return partial_md_path

def get_pdf_size_mb(pdf_path: str) -> float:
    """Get the size of a PDF file in megabytes."""
    return os.path.getsize(pdf_path) / (1024 * 1024)

def split_pdf(pdf_path: str, max_size_mb: float = 45.0) -> list:
    """
    Split a PDF file into smaller chunks, each under the specified max size.
    Returns a list of paths to the temporary PDF files.
    """
    # Read the original PDF
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    total_pages = len(pdf_reader.pages)
    
    # Create a temporary directory for split files
    temp_dir = tempfile.mkdtemp()
    split_files = []
    
    # Start with an estimate of pages per chunk
    # A very rough estimate: if 100 pages is X MB, then max_size_mb would be approximately (max_size_mb * 100) / X pages
    file_size_mb = get_pdf_size_mb(pdf_path)
    pages_per_mb = total_pages / file_size_mb
    estimated_pages_per_chunk = int(max_size_mb * pages_per_mb * 0.9)  # 0.9 as safety factor
    
    # Ensure at least 1 page per chunk
    pages_per_chunk = max(1, estimated_pages_per_chunk)
    
    # Split the PDF
    current_page = 0
    chunk_number = 0
    
    while current_page < total_pages:
        # Create a new PDF writer
        pdf_writer = PyPDF2.PdfWriter()
        
        # Calculate end page for this chunk
        end_page = min(current_page + pages_per_chunk, total_pages)
        
        # Add pages to the writer
        for page_num in range(current_page, end_page):
            pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Save the chunk
        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_number}.pdf")
        with open(chunk_path, 'wb') as f:
            pdf_writer.write(f)
        
        # Check if the chunk is still too large
        chunk_size_mb = get_pdf_size_mb(chunk_path)
        if chunk_size_mb > max_size_mb and (end_page - current_page) > 1:
            # If the chunk is too large and has more than 1 page, delete it and retry with fewer pages
            os.remove(chunk_path)
            # Reduce the pages per chunk and try again
            pages_per_chunk = max(1, int(pages_per_chunk * 0.7))
            continue
        
        # Add to the list and move to the next chunk
        split_files.append(chunk_path)
        current_page = end_page
        chunk_number += 1
    
    return split_files, temp_dir

def process_pdf_chunk(pdf_path: str, client: Mistral, output_dir: str, page_offset: int) -> str:
    """Process a single PDF chunk and return the path to the partial results file."""
    # Confirm PDF file exists
    pdf_file = Path(pdf_path)
    if not pdf_file.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Upload and process PDF
    uploaded_file = client.files.upload(
        file={
            "file_name": pdf_file.stem,
            "content": pdf_file.read_bytes(),
        },
        purpose="ocr",
    )
    
    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
    pdf_response = client.ocr.process(
        document=DocumentURLChunk(document_url=signed_url.url), 
        model="mistral-ocr-latest", 
        include_image_base64=True
    )
    
    # Save partial results
    return save_ocr_results(pdf_response, output_dir, page_offset)

def merge_partial_results(output_dir: str, partial_files: list) -> None:
    """Merge partial markdown results into a single complete file."""
    all_content = []
    
    # Read all partial files in order
    for partial_file in sorted(partial_files):
        with open(partial_file, 'r', encoding='utf-8') as f:
            content = f.read()
            all_content.append(content)
    
    # Write the complete file
    with open(os.path.join(output_dir, "complete.md"), 'w', encoding='utf-8') as f:
        f.write("\n\n".join(all_content))

def process_pdf(pdf_path, api_key, progress_callback=None, output_base_dir=None):
    # Initialize client
    client = Mistral(api_key=api_key)
    
    # Create output directory name
    pdf_file = Path(pdf_path)
    
    # 使用指定的保存路径或默认路径，并使用国际化的目录名称前缀
    ocr_dir_prefix = _("ocr_result_dir")
    if output_base_dir:
        output_dir = os.path.join(output_base_dir, f"{ocr_dir_prefix}{pdf_file.stem}")
    else:
        output_dir = f"{ocr_dir_prefix}{pdf_file.stem}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if the PDF needs splitting
    pdf_size_mb = get_pdf_size_mb(pdf_path)
    
    if pdf_size_mb <= 45:  # Using 45MB as a safe threshold
        # Process the PDF directly
        if progress_callback:
            progress_callback(0, 1)
        process_pdf_chunk(pdf_path, client, output_dir, 0)
        if progress_callback:
            progress_callback(1, 1)
        return output_dir
    else:
        # Split the PDF and process chunks
        if progress_callback:
            progress_callback(0, 1, f"PDF size ({pdf_size_mb:.2f} MB) exceeds 50MB limit. Splitting into smaller chunks...")
        split_files, temp_dir = split_pdf(pdf_path)
        
        try:
            partial_results = []
            page_offset = 0
            
            # Process each chunk
            for i, chunk_path in enumerate(split_files):
                if progress_callback:
                    progress_callback(i, len(split_files), f"Processing chunk {i+1}/{len(split_files)}...")
                chunk_size_mb = get_pdf_size_mb(chunk_path)
                
                # Get number of pages in this chunk
                with open(chunk_path, 'rb') as f:
                    chunk_reader = PyPDF2.PdfReader(f)
                    chunk_pages = len(chunk_reader.pages)
                
                # Process the chunk
                partial_file = process_pdf_chunk(chunk_path, client, output_dir, page_offset)
                partial_results.append(partial_file)
                
                # Update page offset for the next chunk
                page_offset += chunk_pages
            
            # Merge results
            if progress_callback:
                progress_callback(len(split_files), len(split_files), "Merging results...")
            merge_partial_results(output_dir, partial_results)
            
            return output_dir
            
        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir)

class Config:
    """Class to handle configuration and API key persistence"""
    CONFIG_FILE = Path.home() / "mistral_ocr_config.json"
    
    @classmethod
    def save_api_key(cls, api_key):
        """Save API key to config file"""
        config = {"api_key": api_key}
        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    
    @classmethod
    def load_api_key(cls):
        """Load API key from config file"""
        if not cls.CONFIG_FILE.exists():
            return None
        try:
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return config.get("api_key")
        except:
            return None

class OCRApp(tk.Tk if not TKDND_AVAILABLE else TkinterDnD.Tk):
    """Main application window with drag and drop support"""
    def __init__(self):
        # 初始化国际化系统
        i18n.initialize()
        
        super().__init__()
        self.title(_("app_title"))
        self.geometry("800x800")
        self.minsize(800, 800)
        
        # 设置图标和风格
        self.style = ttk.Style()
        self.style.configure("TButton", font=("微软雅黑", 10))
        self.style.configure("TProgressbar", thickness=10)
        
        # 应用主题颜色
        self.configure(bg="#f5f5f5")
        
        self.create_widgets()
        self.api_key = Config.load_api_key()
        if not self.api_key:
            self.prompt_for_api_key()
        
        # 初始化文件队列
        self.file_queue = []
        self.current_file_index = 0
        self.processing = False
        self.output_dirs = []
    
    def create_widgets(self):
        """创建所有GUI元素"""
        # 顶部标题
        header_frame = tk.Frame(self, bg="#3a7ca5", padx=10, pady=10)
        header_frame.pack(fill=tk.X)
        
        tk.Label(
            header_frame, 
            text=_("header_title"),
            font=("微软雅黑", 16, "bold"),
            fg="white",
            bg="#3a7ca5"
        ).pack(side=tk.LEFT)
        
        # 语言选择下拉菜单
        language_frame = tk.Frame(header_frame, bg="#3a7ca5")
        language_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(
            language_frame,
            text=_("language") + ":",
            font=("微软雅黑", 9),
            bg="#3a7ca5",
            fg="white"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.language_var = tk.StringVar()
        self.language_var.set(i18n.current_lang)
        
        self.language_dropdown = ttk.Combobox(
            language_frame,
            textvariable=self.language_var,
            values=[f"{code} - {name}" for code, name in i18n.LANGUAGES.items()],
            state="readonly",
            width=12,
            font=("微软雅黑", 9)
        )
        self.language_dropdown.pack(side=tk.LEFT)
        self.language_dropdown.bind("<<ComboboxSelected>>", self.change_language)
        
        # 创建主体框架
        main_frame = tk.Frame(self, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # 创建拖放区域框架
        drop_frame = tk.Frame(
            main_frame, 
            bd=2, 
            relief=tk.GROOVE,
            bg="#f0f0f0", 
            height=150
        )
        drop_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建用于放置图标和文字的内部框架
        drop_content = tk.Frame(drop_frame, bg="#f0f0f0")
        drop_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 拖放区域指示文字
        self.drop_label = tk.Label(
            drop_content, 
            text=_("drop_area_hint"),
            font=("微软雅黑", 14),
            bg="#f0f0f0",
            fg="#333333"
        )
        self.drop_label.pack(pady=(0, 15))
        
        # 添加图标指示 - 使用pack替代place以提高稳定性
        icon_label = tk.Label(
            drop_content,
            text="📄➡️📋",
            font=("Arial", 24),
            bg="#f0f0f0",
            fg="#666666"
        )
        icon_label.pack()
        
        # 文件拖放功能设置 - 将整个框架注册为拖放目标
        if TKDND_AVAILABLE:
            drop_frame.drop_target_register(DND_FILES)
            drop_frame.dnd_bind('<<Drop>>', self.on_drop)
            self.drop_label.bind("<ButtonPress-1>", self.on_click)
            icon_label.bind("<ButtonPress-1>", self.on_click)
            drop_content.bind("<ButtonPress-1>", self.on_click)
        
        # 任务队列区域
        queue_frame = tk.LabelFrame(main_frame, text=_("queue_label"), font=("微软雅黑", 10, "bold"), bg="#f5f5f5")
        queue_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建滚动条和列表框
        scrollbar = tk.Scrollbar(queue_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(
            queue_frame, 
            height=5, 
            font=("微软雅黑", 9),
            selectbackground="#d0e0ff",
            activestyle="none",
            yscrollcommand=scrollbar.set
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.file_listbox.yview)
        
        # 任务列表操作按钮
        list_buttons_frame = tk.Frame(queue_frame, bg="#f5f5f5")
        list_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            list_buttons_frame,
            text=_("add_files"),
            command=self.add_files,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            list_buttons_frame,
            text=_("remove_selected"),
            command=self.remove_selected,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            list_buttons_frame,
            text=_("clear_queue"),
            command=self.clear_queue,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # 输出设置区域
        output_frame = tk.LabelFrame(main_frame, text=_("output_settings"), font=("微软雅黑", 10, "bold"), bg="#f5f5f5")
        output_frame.pack(fill=tk.X, pady=10)
        
        # 输出路径选择
        output_path_frame = tk.Frame(output_frame, bg="#f5f5f5")
        output_path_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(
            output_path_frame,
            text=_("save_location"),
            font=("微软雅黑", 9),
            bg="#f5f5f5"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.output_path_var = tk.StringVar()
        self.output_path_var.set(os.path.abspath(os.curdir))  # 默认为当前目录
        
        output_entry = tk.Entry(
            output_path_frame,
            textvariable=self.output_path_var,
            font=("微软雅黑", 9),
            width=40,
            state="readonly"
        )
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(
            output_path_frame,
            text=_("browse_button"),
            command=self.choose_output_dir,
            width=8
        ).pack(side=tk.LEFT)
        
        # 进度区域
        progress_frame = tk.LabelFrame(main_frame, text=_("progress_label"), font=("微软雅黑", 10, "bold"), bg="#f5f5f5")
        progress_frame.pack(fill=tk.X, pady=10)
        
        # 总体进度
        tk.Label(
            progress_frame, 
            text=_("total_progress"), 
            font=("微软雅黑", 9),
            bg="#f5f5f5"
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        self.total_progress = ttk.Progressbar(
            progress_frame, 
            orient="horizontal", 
            length=300, 
            mode="determinate",
            style="TProgressbar"
        )
        self.total_progress.pack(fill=tk.X, padx=5, pady=2)
        
        # 当前文件进度
        tk.Label(
            progress_frame, 
            text=_("current_file"), 
            font=("微软雅黑", 9),
            bg="#f5f5f5"
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        self.file_progress = ttk.Progressbar(
            progress_frame, 
            orient="horizontal", 
            length=300, 
            mode="determinate",
            style="TProgressbar"
        )
        self.file_progress.pack(fill=tk.X, padx=5, pady=2)
        
        # 状态信息
        self.status_label = tk.Label(
            progress_frame, 
            text=_("ready"), 
            font=("微软雅黑", 9),
            fg="#555555",
            bg="#f5f5f5"
        )
        self.status_label.pack(anchor=tk.W, padx=5, pady=5)
        
        # 按钮区域
        button_frame = tk.Frame(main_frame, bg="#f5f5f5")
        button_frame.pack(pady=10)
        
        self.process_button = ttk.Button(
            button_frame, 
            text=_("start_process"), 
            command=self.process_queue, 
            width=15
        )
        self.process_button.pack(side=tk.LEFT, padx=10)
        
        self.api_button = ttk.Button(
            button_frame, 
            text=_("set_api_key"), 
            command=self.prompt_for_api_key, 
            width=15
        )
        self.api_button.pack(side=tk.LEFT, padx=10)
        
        self.results_button = ttk.Button(
            button_frame, 
            text=_("browse_results"), 
            command=self.browse_results, 
            width=15, 
            state=tk.DISABLED
        )
        self.results_button.pack(side=tk.LEFT, padx=10)
        
        # 底部版权信息
        tk.Label(
            self, 
            text=_("copyright"),
            font=("微软雅黑", 8),
            fg="#999999",
            bg="#f5f5f5"
        ).pack(side=tk.BOTTOM, pady=5)
    
    def on_drop(self, event):
        """处理文件拖放"""
        files = event.data
        
        # 在Windows上可能会将多个文件路径作为一个字符串返回
        # 处理这种情况并分割它们
        if isinstance(files, str):
            # 移除可能的花括号或引号
            files = files.strip('{}')
            # 检查是否有多个文件（以空格分隔）
            if ' ' in files and ('"' in files or "'"):
                # 按照引号分割多个文件
                import re
                file_paths = re.findall(r'\"(.+?)\"', files)
                if not file_paths:
                    file_paths = re.findall(r'\'(.+?)\'', files)
                if not file_paths:
                    file_paths = [files]  # 回退到单个文件
            else:
                # 单个文件
                file_paths = [files.strip('"').strip("'")]
        else:
            file_paths = [files]
        
        # 处理拖放的所有文件
        added_count = 0
        for file_path in file_paths:
            if file_path.lower().endswith('.pdf'):
                self.add_file_to_queue(file_path)
                added_count += 1
        
        # 提供视觉反馈
        if added_count > 0:
            self.status_label.config(text=f"已添加 {added_count} 个PDF文件到队列")
        else:
            messagebox.showerror("无效文件", "请拖放PDF文件。")
    
    def on_click(self, event):
        """处理点击打开文件对话框"""
        file_paths = filedialog.askopenfilenames(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf")],
            initialdir=os.path.expanduser("~\\Documents")
        )
        added_count = 0
        for file_path in file_paths:
            self.add_file_to_queue(file_path)
            added_count += 1
        
        if added_count > 0:
            self.status_label.config(text=f"已添加 {added_count} 个PDF文件到队列")
    
    def add_file_to_queue(self, file_path):
        """添加文件到队列并更新显示"""
        if file_path not in self.file_queue:  # 避免重复添加
            self.file_queue.append(file_path)
            file_size = get_pdf_size_mb(file_path)
            self.file_listbox.insert(
                tk.END, 
                f"{os.path.basename(file_path)} ({file_size:.1f} MB)"
            )
    
    def add_files(self):
        """批量添加文件到队列"""
        file_paths = filedialog.askopenfilenames(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf")],
            initialdir=os.path.expanduser("~\\Documents")
        )
        added_count = 0
        for file_path in file_paths:
            self.add_file_to_queue(file_path)
            added_count += 1
        
        if added_count > 0:
            self.status_label.config(text=f"已添加 {added_count} 个PDF文件到队列")
    
    def remove_selected(self):
        """移除选定的文件"""
        selected_indices = self.file_listbox.curselection()
        for index in reversed(selected_indices):
            self.file_listbox.delete(index)
            del self.file_queue[index]
        self.status_label.config(text="选定文件已移除")
    
    def clear_queue(self):
        """清空文件队列"""
        self.file_listbox.delete(0, tk.END)
        self.file_queue.clear()
        self.status_label.config(text="文件队列已清空")
    
    def prompt_for_api_key(self):
        """提示用户输入API密钥"""
        api_dialog = tk.Toplevel(self)
        api_dialog.title(_("api_key_title"))
        api_dialog.geometry("480x240")
        api_dialog.transient(self)
        api_dialog.grab_set()
        api_dialog.resizable(False, False)
        
        # 对话框内容
        tk.Label(
            api_dialog, 
            text=_("api_key_prompt"), 
            font=("微软雅黑", 12)
        ).pack(pady=(15, 5))
        
        # 添加申请API链接
        link_frame = tk.Frame(api_dialog)
        link_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(
            link_frame,
            text=_("no_api_key"),
            font=("微软雅黑", 9),
            fg="#555555"
        ).pack(side=tk.LEFT)
        
        link_label = tk.Label(
            link_frame,
            text=_("apply_here"),
            font=("微软雅黑", 9, "underline"),
            fg="#0066cc",
            cursor="hand2"
        )
        link_label.pack(side=tk.LEFT)
        
        def open_mistral_website(event):
            import webbrowser
            webbrowser.open("https://console.mistral.ai/")
        
        link_label.bind("<Button-1>", open_mistral_website)
        
        # 添加API激活提示
        tk.Label(
            api_dialog,
            text=_("api_activation_note"),
            font=("微软雅黑", 9),
            fg="#FF5500"
        ).pack(pady=(2, 5))
        
        tk.Label(
            api_dialog,
            text=_("api_security_note"),
            font=("微软雅黑", 9),
            fg="#555555"
        ).pack()
        
        api_var = tk.StringVar()
        if self.api_key:
            api_var.set(self.api_key)
        
        entry_frame = tk.Frame(api_dialog)
        entry_frame.pack(pady=15, fill=tk.X, padx=20)
        
        entry = tk.Entry(
            entry_frame, 
            textvariable=api_var, 
            width=50, 
            show="•",
            font=("Consolas", 10)
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 显示/隐藏密钥切换
        self.show_key = False
        
        def toggle_show():
            self.show_key = not self.show_key
            entry.config(show="" if self.show_key else "•")
            show_btn.config(text=_("hide") if self.show_key else _("show"))
        
        show_btn = ttk.Button(entry_frame, text=_("show"), width=5, command=toggle_show)
        show_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        button_frame = tk.Frame(api_dialog)
        button_frame.pack(pady=15)
        
        def save_key():
            key = api_var.get().strip()
            if key:
                self.api_key = key
                Config.save_api_key(key)
                api_dialog.destroy()
                self.status_label.config(text=_("status_api_key_saved"))
            else:
                messagebox.showerror(_("error"), _("error_empty_api_key"), parent=api_dialog)
        
        ttk.Button(
            button_frame, 
            text=_("save"), 
            command=save_key, 
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame, 
            text=_("cancel"), 
            command=api_dialog.destroy, 
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # 将对话框居中显示
        api_dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - api_dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - api_dialog.winfo_height()) // 2
        api_dialog.geometry(f"+{x}+{y}")
        
        # 设置焦点
        entry.focus_set()
    
    def update_progress(self, current, total, message=None):
        """更新进度条和状态消息"""
        progress_value = int((current / total) * 100)
        self.file_progress["value"] = progress_value
        
        if message:
            self.status_label.config(text=message)
        else:
            self.status_label.config(text=f"处理中: {progress_value}%")
        
        self.update_idletasks()
    
    def process_queue(self):
        """处理文件队列"""
        if not self.file_queue:
            messagebox.showerror("错误", "请先添加一个或多个PDF文件")
            return
        
        if not self.api_key:
            messagebox.showerror("错误", "请先设置您的API密钥")
            self.prompt_for_api_key()
            return
        
        # 重置UI状态
        self.total_progress["value"] = 0
        self.file_progress["value"] = 0
        self.status_label.config(text="正在启动...")
        self.process_button.config(state=tk.DISABLED)
        self.results_button.config(state=tk.DISABLED)
        self.output_dirs.clear()
        
        # 在单独的线程中处理以保持UI响应
        def process_thread():
            try:
                total_files = len(self.file_queue)
                for index, file_path in enumerate(self.file_queue):
                    self.current_file_index = index
                    self.status_label.config(text=f"正在处理文件 {index + 1}/{total_files}: {os.path.basename(file_path)}")
                    output_dir = process_pdf(
                        file_path, 
                        self.api_key, 
                        self.update_progress,
                        self.output_path_var.get()  # 使用用户选择的输出路径
                    )
                    self.output_dirs.append(output_dir)
                    
                    # 更新总体进度
                    self.total_progress["value"] = int(((index + 1) / total_files) * 100)
                
                # 处理后更新UI
                self.status_label.config(text="所有文件处理完成!")
                self.results_button.config(state=tk.NORMAL)
                
                # 提示用户处理完
                messagebox.showinfo("处理完成", "所有PDF文件转换已完成!")
                self.status_label.config(text=_("success_all_files_done"))
                
            except Exception as e:
                messagebox.showerror("错误", f"发生错误: {str(e)}")
                self.status_label.config(text="处理失败")
            finally:
                self.process_button.config(state=tk.NORMAL)
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def browse_results(self):
        """在文件资源管理器中打开输出目录"""
        if self.output_dirs:
            for output_dir in self.output_dirs:
                if os.path.exists(output_dir):
                    # 跨平台打开目录
                    if os.name == 'nt':  # Windows
                        os.startfile(os.path.abspath(output_dir))
                    elif os.name == 'posix':  # macOS, Linux
                        if os.uname().sysname == 'Darwin':  # macOS
                            subprocess.call(['open', output_dir])
                        else:  # Linux
                            subprocess.call(['xdg-open', output_dir])
        else:
            messagebox.showerror(_("error"), _("error_no_output_dir"))
    
    def choose_output_dir(self):
        """选择输出目录"""
        selected_dir = filedialog.askdirectory(
            title=_("save_location"),
            initialdir=self.output_path_var.get() or os.path.expanduser("~\\Documents")
        )
        if selected_dir:
            self.output_path_var.set(selected_dir)
            self.status_label.config(text=_("status_output_set").format(selected_dir))
    
    def change_language(self, event=None):
        """切换用户界面语言"""
        selected = self.language_var.get()
        # 从下拉框的值中提取语言代码 (格式: "zh_CN - 简体中文")
        lang_code = selected.split(' - ')[0]
        
        if lang_code in i18n.LANGUAGES:
            # 更改语言
            i18n.change_language(lang_code)
            # 保存用户偏好
            i18n.save_language_preference(lang_code)
            
            # 更新UI
            self.update_ui_language()
            
            # 显示确认消息
            if lang_code == "zh_CN":
                self.status_label.config(text="语言已更改为简体中文")
            elif lang_code == "en_US":
                self.status_label.config(text="Language changed to English")
            elif lang_code == "ja_JP":
                self.status_label.config(text="言語が日本語に変更されました")
            elif lang_code == "ko_KR":
                self.status_label.config(text="언어가 한국어로 변경되었습니다")
    
    def update_ui_language(self):
        """更新用户界面的语言"""
        # 主窗口标题
        self.title(_("app_title"))
        
        # 销毁所有现有控件
        for widget in self.winfo_children():
            widget.destroy()
        
        # 重新创建所有控件
        self.create_widgets()
        
        # 恢复状态
        if hasattr(self, 'results_button') and self.output_dirs:
            self.results_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    # 显示欢迎信息
    print("启动 Mistral OCR PDF 转换工具...")
    
    if not TKDND_AVAILABLE:
        print("警告: tkinterdnd2 模块未安装。拖放功能将不可用。")
        print("要启用拖放功能，请安装: pip install tkinterdnd2")
    
    # 启动应用
    app = OCRApp()
    
    # 设置窗口图标(如果有)
    try:
        app.iconbitmap("icon.ico")
    except:
        pass
    
    app.mainloop()
