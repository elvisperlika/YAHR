import os
import re
import subprocess

DOCS_DIR = "docs"
INDEX_FILE = os.path.join(DOCS_DIR, "index.md")
INCLUDES_DIR = os.path.join(DOCS_DIR, "_includes")
OUTPUT_MD = os.path.join(DOCS_DIR, "yahr_documentation.md")


def combine_docs():
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove frontmatter
    content = re.sub(r"^---\n.*?---\n", "", content, flags=re.DOTALL)

    def replace_include(match):
        filename = match.group(1).strip()
        filepath = os.path.join(INCLUDES_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return match.group(0)

    # Replace all {% include filename.md %} with actual content
    combined_content = re.sub(r"\{%\s*include\s+(.*?)\s*%\}", replace_include, content)

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(combined_content)

    print(f"Combined markdown written to {OUTPUT_MD}")


if __name__ == "__main__":
    combine_docs()
