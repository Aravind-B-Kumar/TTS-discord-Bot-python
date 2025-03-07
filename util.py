import buttons 

class paginator(buttons.Paginator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def clean_code(content):
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]
    else:
        return content
