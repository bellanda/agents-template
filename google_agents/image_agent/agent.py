import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))


from google.adk.agents import Agent

from google_agents.image_agent.tools import generate_image

root_agent = Agent(
    name="image_agent_litellm",
    model="gemini-2.5-flash-preview-05-20",
    description="Generates images using Google's Imagen 3 model.",
    instruction="You are a helpful AI image generation assistant. "
    "Use the 'generate_image' tool to create images based on user descriptions. "
    "Always ask for clarification if the prompt is unclear or too vague. "
    "When calling generate_image, always provide both parameters: prompt and number_of_images. "
    "If the user doesn't specify how many images, use 1 as the default. "
    "The maximum number of images is 4. "
    "Present the generated images in a friendly and helpful manner. "
    "If the user asks for image generation, always use the tool to create the image.",
    tools=[generate_image],
)
