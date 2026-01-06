from src.data_word import *
import base64
import io
import matplotlib.pyplot as plt
from PIL import Image

file_path = "data_test/test.docx"

content = export_word_content(file_path)
image_base64 = content['images'][1]['base64']

# Convert base64 to image
image_data = base64.b64decode(image_base64)
image = Image.open(io.BytesIO(image_data))

# Display the image
plt.figure(figsize=(10, 8))
plt.imshow(image)
plt.axis('off')  # Hide axes
plt.title('Extracted Image from Word Document')
plt.show()

print(f"Image size: {image.size}")
print(f"Image mode: {image.mode}")