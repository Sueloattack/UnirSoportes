import pypdf
import sys

pdf_path = sys.argv[1]
reader = pypdf.PdfReader(pdf_path)
text = reader.pages[0].extract_text()
print(text[:3000])
