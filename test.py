# from llms.google import generate_image_imagen3

# image = generate_image_imagen3("And dragon fighting with a dog in the moon", 1)
# image.save("gemini-native-image.png")
from llms.azure import call_azure_llm

print(call_azure_llm("o4-mini", "Boa tarde!"))
