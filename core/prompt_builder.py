def build_prompt(log_text, template_name):
    with open(f"prompts/{template_name}", "r") as f:
        template = f.read()
    return template.replace("{{LOGS}}", log_text)