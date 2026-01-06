from src.data_pdf import *

file_path = "data_test/test.pdf"

content = parse_pdf_from_path(file_path)

print(content)