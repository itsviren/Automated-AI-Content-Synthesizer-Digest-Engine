import html


def markdown_text(value):
    # Prevent source text from injecting Markdown links, headings, or HTML.
    value = " ".join(str(value).split())
    for char in "\\`*_{}[]<>#!|":
        value = value.replace(char, "\\" + char)
    return value


def markdown(digest):
    lines = [f"# Daily Digest — {digest['day']}", "", f"Profile: {digest['profile']}", "",
             "Summaries are generated from source text; consult the linked originals.", ""]
    if not digest["items"]:
        lines += ["No new articles were found.", ""]
    for item in digest["items"]:
        lines += [f"## {markdown_text(item['title'])}", "", f"Category: {markdown_text(item['category'])}",
                  f"Source: <{item['url'].replace('>', '%3E').replace('<', '%3C')}>",
                  f"Method: {item['method']}", "", markdown_text(item["summary"]), ""]
        lines += ["- " + markdown_text(b) for b in item["takeaways"]]
        lines += [""]
    if digest["warnings"]:
        lines += ["## Source warnings", ""] + ["- " + markdown_text(w) for w in digest["warnings"]]
    return "\n".join(lines) + "\n"


def export(digest, directory):
    directory.mkdir(parents=True, exist_ok=True)
    filename = digest["id"]
    md = markdown(digest)
    (directory / f"{filename}.md").write_text(md, encoding="utf-8")
    # This portable export deliberately does not execute Markdown or source HTML.
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Digest {html.escape(digest["day"])}</title>'
            '<style>body{max-width:850px;margin:40px auto;padding:20px;font:16px/1.6 system-ui}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
            f'<pre>{html.escape(md)}</pre></html>')
    (directory / f"{filename}.html").write_text(page, encoding="utf-8")
