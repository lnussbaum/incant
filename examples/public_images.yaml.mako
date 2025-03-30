<%
import json
import platform
import re

# Load images from examples/data/images.json file
with open("examples/data/images.json", "r", encoding="utf-8") as f:
    images = json.load(f)

# Determine current architecture
current_arch = platform.machine()

# Function to sanitize instance names
def sanitize_name(name):
    # Convert to lowercase, replace non-alphanumeric characters with hyphens
    return re.sub(r'[^a-z0-9-]', '-', name.lower())

# Filter images for foreign architectures
filtered_images = [
    img for img in images
    if img.get("architecture") == current_arch and img.get("aliases")
]

# Function to get the shortest alias name
def get_shortest_alias(aliases):
    return min(aliases, key=lambda alias: len(alias["name"]))["name"]
%>

instances:
% for img in filtered_images:
  <% vm = img['type'] == 'virtual-machine' %>
  ${sanitize_name(get_shortest_alias(img["aliases"]))}${'-vm' if vm else ''}:
    image: images:${get_shortest_alias(img["aliases"])}
    vm: ${"true" if vm else "false"}
    wait: true
% endfor
