"""
国际化资源模块 (i18n.py)
提供多语言支持功能
"""
import os
import json
from pathlib import Path

# 语言资源目录
RESOURCE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "locales"

# 确保资源目录存在
os.makedirs(RESOURCE_DIR, exist_ok=True)

# 支持的语言
LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English",
    "ja_JP": "日本語",
    "ko_KR": "한국어"
}

# 当前语言
current_lang = "zh_CN"  # 默认为中文

# 语言资源缓存
_resources = {}

def load_language_resource(lang_code):
    """加载指定语言的资源文件"""
    if lang_code in _resources:
        return _resources[lang_code]
    
    resource_path = RESOURCE_DIR / f"{lang_code}.json"
    
    # 如果语言资源文件不存在，返回空字典
    if not resource_path.exists():
        _resources[lang_code] = {}
        return {}
    
    try:
        with open(resource_path, 'r', encoding='utf-8') as f:
            _resources[lang_code] = json.load(f)
        return _resources[lang_code]
    except Exception as e:
        print(f"加载语言资源失败: {e}")
        _resources[lang_code] = {}
        return {}

def get_text(key, default=None):
    """获取当前语言的文本"""
    if current_lang not in _resources:
        load_language_resource(current_lang)
    
    # 如果资源中有对应的key，返回其值
    if key in _resources.get(current_lang, {}):
        return _resources[current_lang][key]
    
    # 如果当前语言中找不到，尝试使用默认语言
    if current_lang != "zh_CN" and "zh_CN" in _resources:
        if key in _resources["zh_CN"]:
            return _resources["zh_CN"][key]
    
    # 如果都找不到，返回默认值或key本身
    return default if default is not None else key

def change_language(lang_code):
    """切换语言"""
    global current_lang
    if lang_code in LANGUAGES:
        current_lang = lang_code
        # 确保加载新的语言资源
        if lang_code not in _resources:
            load_language_resource(lang_code)
        return True
    return False

def save_language_preference(lang_code):
    """保存语言偏好到配置文件"""
    config_path = Path.home() / "mistral_ocr_config.json"
    
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            pass
    
    config["language"] = lang_code
    
    with open(config_path, 'w') as f:
        json.dump(config, f)

def load_language_preference():
    """从配置文件加载语言偏好"""
    config_path = Path.home() / "mistral_ocr_config.json"
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("language")
    except:
        return None

# 初始化语言资源文件（如果它们不存在）
def init_language_resources():
    """初始化默认语言资源文件"""
    # 中文资源
    zh_resource = {
        "app_title": "Mistral OCR PDF 转换工具",
        "header_title": "Mistral OCR PDF 文档识别工具",
        "drop_area_hint": "拖放PDF文件到此处或点击浏览",
        "queue_label": "任务队列",
        "add_files": "添加文件",
        "remove_selected": "移除所选",
        "clear_queue": "清空队列",
        "output_settings": "输出设置",
        "save_location": "保存位置:",
        "browse_button": "浏览...",
        "progress_label": "处理进度",
        "total_progress": "总体进度:",
        "current_file": "当前文件:",
        "start_process": "开始处理",
        "set_api_key": "设置API密钥",
        "browse_results": "浏览结果",
        "ready": "准备就绪",
        "copyright": "© 2025 Mistral OCR 转换工具",
        "api_key_title": "输入API密钥",
        "api_key_prompt": "请输入您的Mistral AI API密钥:",
        "no_api_key": "没有API密钥? ",
        "apply_here": "点击这里申请",
        "api_activation_note": "注意: 新申请的API密钥可能需要几分钟才能生效",
        "api_security_note": "密钥将被安全保存在您的用户目录中",
        "show": "显示",
        "hide": "隐藏",
        "save": "保存",
        "cancel": "取消",
        "error": "错误",
        "error_no_files": "请先添加一个或多个PDF文件",
        "error_no_api_key": "请先设置您的API密钥",
        "error_invalid_file": "无效文件",
        "error_drag_pdf": "请拖放PDF文件。",
        "error_process_failed": "处理失败",
        "error_empty_api_key": "API密钥不能为空",
        "error_no_output_dir": "未找到输出目录",
        "success_process_complete": "处理完成",
        "success_all_files_done": "所有PDF文件转换已完成!",
        "status_added_files": "已添加 {0} 个PDF文件到队列",
        "status_selected_removed": "选定文件已移除",
        "status_queue_cleared": "文件队列已清空",
        "status_output_set": "已设置保存位置: {0}",
        "status_processing": "处理中: {0}%",
        "status_init": "正在启动...",
        "status_api_key_saved": "API密钥已保存",
        "status_processing_file": "正在处理文件 {0}/{1}: {2}",
        "status_all_complete": "所有文件处理完成!",
        "status_file_exceed_limit": "PDF大小 ({0:.2f} MB) 超过50MB限制。正在分割为更小的块...",
        "status_processing_chunk": "正在处理块 {0}/{1}...",
        "status_merging": "正在合并结果...",
        "language": "语言",
        "lang_zh_CN": "简体中文",
        "lang_en_US": "English",
        "lang_ja_JP": "日本語",
        "lang_ko_KR": "한국어",
        "ocr_result_dir": "ocr_结果_",
        "page_title": "第 {0} 页",
        "complete_file": "完整结果.md",
        "part_file": "部分_{0}.md",
        "images_dir": "图片"
    }
    
    # 英文资源
    en_resource = {
        "app_title": "Mistral OCR PDF Converter",
        "header_title": "Mistral OCR PDF Document Recognition Tool",
        "drop_area_hint": "Drag & drop PDF files here or click to browse",
        "queue_label": "Task Queue",
        "add_files": "Add Files",
        "remove_selected": "Remove Selected",
        "clear_queue": "Clear Queue",
        "output_settings": "Output Settings",
        "save_location": "Save Location:",
        "browse_button": "Browse...",
        "progress_label": "Processing Progress",
        "total_progress": "Total Progress:",
        "current_file": "Current File:",
        "start_process": "Start Processing",
        "set_api_key": "Set API Key",
        "browse_results": "Browse Results",
        "ready": "Ready",
        "copyright": "© 2025 Mistral OCR Converter Tool",
        "api_key_title": "Enter API Key",
        "api_key_prompt": "Please enter your Mistral AI API key:",
        "no_api_key": "No API key? ",
        "apply_here": "Apply here",
        "api_activation_note": "Note: Newly applied API key may take a few minutes to activate",
        "api_security_note": "Your key will be securely saved in your user directory",
        "show": "Show",
        "hide": "Hide",
        "save": "Save",
        "cancel": "Cancel",
        "error": "Error",
        "error_no_files": "Please add one or more PDF files first",
        "error_no_api_key": "Please set your API key first",
        "error_invalid_file": "Invalid File",
        "error_drag_pdf": "Please drag and drop PDF files.",
        "error_process_failed": "Processing failed",
        "error_empty_api_key": "API key cannot be empty",
        "error_no_output_dir": "Output directory not found",
        "success_process_complete": "Processing Complete",
        "success_all_files_done": "All PDF files have been converted!",
        "status_added_files": "Added {0} PDF files to queue",
        "status_selected_removed": "Selected files removed",
        "status_queue_cleared": "File queue cleared",
        "status_output_set": "Save location set: {0}",
        "status_processing": "Processing: {0}%",
        "status_init": "Initializing...",
        "status_api_key_saved": "API key saved",
        "status_processing_file": "Processing file {0}/{1}: {2}",
        "status_all_complete": "All files processing completed!",
        "status_file_exceed_limit": "PDF size ({0:.2f} MB) exceeds 50MB limit. Splitting into smaller chunks...",
        "status_processing_chunk": "Processing chunk {0}/{1}...",
        "status_merging": "Merging results...",
        "language": "Language",
        "lang_zh_CN": "简体中文",
        "lang_en_US": "English",
        "lang_ja_JP": "日本語",
        "lang_ko_KR": "한국어",
        "ocr_result_dir": "ocr_results_",
        "page_title": "Page {0}",
        "complete_file": "complete.md",
        "part_file": "part_{0}.md",
        "images_dir": "images"
    }
    
    # 日文资源
    ja_resource = {
        "app_title": "Mistral OCR PDF コンバーター",
        "header_title": "Mistral OCR PDF 文書認識ツール",
        "drop_area_hint": "PDFファイルをここにドラッグ＆ドロップするか、クリックして参照",
        "queue_label": "タスクキュー",
        "add_files": "ファイル追加",
        "remove_selected": "選択削除",
        "clear_queue": "キュークリア",
        "output_settings": "出力設定",
        "save_location": "保存場所:",
        "browse_button": "参照...",
        "progress_label": "処理進捗",
        "total_progress": "全体進捗:",
        "current_file": "現在のファイル:",
        "start_process": "処理開始",
        "set_api_key": "APIキー設定",
        "browse_results": "結果を表示",
        "ready": "準備完了",
        "copyright": "© 2025 Mistral OCR コンバーターツール",
        "api_key_title": "APIキー入力",
        "api_key_prompt": "Mistral AI APIキーを入力してください:",
        "no_api_key": "APIキーをお持ちでない場合は ",
        "apply_here": "こちらから申請",
        "api_activation_note": "注意: 新しく申請したAPIキーが有効になるまで数分かかる場合があります",
        "api_security_note": "キーはユーザーディレクトリに安全に保存されます",
        "show": "表示",
        "hide": "非表示",
        "save": "保存",
        "cancel": "キャンセル",
        "error": "エラー",
        "error_no_files": "まずPDFファイルを追加してください",
        "error_no_api_key": "まずAPIキーを設定してください",
        "error_invalid_file": "無効なファイル",
        "error_drag_pdf": "PDFファイルをドラッグ＆ドロップしてください。",
        "error_process_failed": "処理に失敗しました",
        "error_empty_api_key": "APIキーを入力してください",
        "error_no_output_dir": "出力ディレクトリが見つかりません",
        "success_process_complete": "処理完了",
        "success_all_files_done": "すべてのPDFファイルの変換が完了しました!",
        "status_added_files": "{0}個のPDFファイルがキューに追加されました",
        "status_selected_removed": "選択したファイルを削除しました",
        "status_queue_cleared": "ファイルキューをクリアしました",
        "status_output_set": "保存場所を設定: {0}",
        "status_processing": "処理中: {0}%",
        "status_init": "初期化中...",
        "status_api_key_saved": "APIキーを保存しました",
        "status_processing_file": "ファイル処理中 {0}/{1}: {2}",
        "status_all_complete": "すべてのファイル処理が完了しました!",
        "status_file_exceed_limit": "PDFサイズ ({0:.2f} MB) が50MB制限を超えています。小さなチャンクに分割します...",
        "status_processing_chunk": "チャンク処理中 {0}/{1}...",
        "status_merging": "結果をマージ中...",
        "language": "言語",
        "lang_zh_CN": "简体中文",
        "lang_en_US": "English",
        "lang_ja_JP": "日本語",
        "lang_ko_KR": "한국어",
        "ocr_result_dir": "ocr_結果_",
        "page_title": "ページ {0}",
        "complete_file": "完全結果.md",
        "part_file": "部分_{0}.md",
        "images_dir": "画像"
    }
    
    # 韩文资源
    ko_resource = {
        "app_title": "Mistral OCR PDF 변환 도구",
        "header_title": "Mistral OCR PDF 문서 인식 도구",
        "drop_area_hint": "PDF 파일을 여기에 끌어다 놓거나 클릭하여 찾아보기",
        "queue_label": "작업 대기열",
        "add_files": "파일 추가",
        "remove_selected": "선택 삭제",
        "clear_queue": "대기열 지우기",
        "output_settings": "출력 설정",
        "save_location": "저장 위치:",
        "browse_button": "찾아보기...",
        "progress_label": "처리 진행",
        "total_progress": "전체 진행:",
        "current_file": "현재 파일:",
        "start_process": "처리 시작",
        "set_api_key": "API 키 설정",
        "browse_results": "결과 보기",
        "ready": "준비됨",
        "copyright": "© 2025 Mistral OCR 변환 도구",
        "api_key_title": "API 키 입력",
        "api_key_prompt": "Mistral AI API 키를 입력하세요:",
        "no_api_key": "API 키가 없으신가요? ",
        "apply_here": "여기서 신청하기",
        "api_activation_note": "참고: 새로 신청한 API 키는 활성화되기까지 몇 분이 걸릴 수 있습니다",
        "api_security_note": "키는 사용자 디렉토리에 안전하게 저장됩니다",
        "show": "표시",
        "hide": "숨기기",
        "save": "저장",
        "cancel": "취소",
        "error": "오류",
        "error_no_files": "먼저 PDF 파일을 추가해주세요",
        "error_no_api_key": "먼저 API 키를 설정해주세요",
        "error_invalid_file": "잘못된 파일",
        "error_drag_pdf": "PDF 파일을 끌어다 놓으세요.",
        "error_process_failed": "처리 실패",
        "error_empty_api_key": "API 키는 비워둘 수 없습니다",
        "error_no_output_dir": "출력 디렉토리를 찾을 수 없습니다",
        "success_process_complete": "처리 완료",
        "success_all_files_done": "모든 PDF 파일 변환이 완료되었습니다!",
        "status_added_files": "{0}개의 PDF 파일이 대기열에 추가되었습니다",
        "status_selected_removed": "선택한 파일이 제거되었습니다",
        "status_queue_cleared": "파일 대기열이 지워졌습니다",
        "status_output_set": "저장 위치 설정: {0}",
        "status_processing": "처리 중: {0}%",
        "status_init": "초기화 중...",
        "status_api_key_saved": "API 키가 저장되었습니다",
        "status_processing_file": "파일 처리 중 {0}/{1}: {2}",
        "status_all_complete": "모든 파일 처리가 완료되었습니다!",
        "status_file_exceed_limit": "PDF 크기 ({0:.2f} MB)가 50MB 제한을 초과합니다. 작은 청크로 분할 중...",
        "status_processing_chunk": "청크 처리 중 {0}/{1}...",
        "status_merging": "결과 병합 중...",
        "language": "언어",
        "lang_zh_CN": "简体中文",
        "lang_en_US": "English",
        "lang_ja_JP": "日本語",
        "lang_ko_KR": "한국어",
        "ocr_result_dir": "ocr_결과_",
        "page_title": "페이지 {0}",
        "complete_file": "전체결과.md",
        "part_file": "부분_{0}.md",
        "images_dir": "이미지"
    }
    
    # 保存语言资源文件
    zh_path = RESOURCE_DIR / "zh_CN.json"
    en_path = RESOURCE_DIR / "en_US.json"
    ja_path = RESOURCE_DIR / "ja_JP.json"
    ko_path = RESOURCE_DIR / "ko_KR.json"
    
    if not zh_path.exists():
        with open(zh_path, 'w', encoding='utf-8') as f:
            json.dump(zh_resource, f, ensure_ascii=False, indent=2)
    
    if not en_path.exists():
        with open(en_path, 'w', encoding='utf-8') as f:
            json.dump(en_resource, f, ensure_ascii=False, indent=2)
    
    if not ja_path.exists():
        with open(ja_path, 'w', encoding='utf-8') as f:
            json.dump(ja_resource, f, ensure_ascii=False, indent=2)
    
    if not ko_path.exists():
        with open(ko_path, 'w', encoding='utf-8') as f:
            json.dump(ko_resource, f, ensure_ascii=False, indent=2)

# 初始化
def initialize():
    """初始化国际化系统"""
    # 创建语言资源文件
    init_language_resources()
    
    # 加载用户语言偏好
    preferred_lang = load_language_preference()
    if preferred_lang and preferred_lang in LANGUAGES:
        change_language(preferred_lang)
    
    # 预加载当前语言资源
    load_language_resource(current_lang)

# 提供简短的别名函数，方便使用
_ = get_text