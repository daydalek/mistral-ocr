
from mistralai import Mistral
from pathlib import Path
import os
import base64
from mistralai import DocumentURLChunk
from mistralai.models import OCRResponse
import PyPDF2
import tempfile
import shutil

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

def process_pdf(pdf_path: str, api_key: str) -> None:
    # Initialize client
    client = Mistral(api_key=api_key)
    
    # Create output directory name
    pdf_file = Path(pdf_path)
    output_dir = f"ocr_results_{pdf_file.stem}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if the PDF needs splitting
    pdf_size_mb = get_pdf_size_mb(pdf_path)
    
    if pdf_size_mb <= 45:  # Using 45MB as a safe threshold
        # Process the PDF directly
        process_pdf_chunk(pdf_path, client, output_dir, 0)
        print(f"OCR processing complete. Results saved in: {output_dir}")
    else:
        # Split the PDF and process chunks
        print(f"PDF size ({pdf_size_mb:.2f} MB) exceeds 50MB limit. Splitting into smaller chunks...")
        split_files, temp_dir = split_pdf(pdf_path)
        
        try:
            partial_results = []
            page_offset = 0
            
            # Process each chunk
            for i, chunk_path in enumerate(split_files):
                print(f"Processing chunk {i+1}/{len(split_files)}...")
                chunk_size_mb = get_pdf_size_mb(chunk_path)
                print(f"  Chunk size: {chunk_size_mb:.2f} MB")
                
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
            print("Merging results...")
            merge_partial_results(output_dir, partial_results)
            print(f"OCR processing complete. Results saved in: {output_dir}")
            
        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # Example usage
    API_KEY = ""
    PDF_PATH = ""
    
    process_pdf(PDF_PATH, API_KEY)
