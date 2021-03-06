#!/usr/bin/python
import nbformat
import datetime
import sys
import os
import argparse
import pathlib
import requests as req
import PIL
from PIL import Image as PIL_image
import io
import pendulum as pm

anki_dir = os.environ["ANKI_PROFILE"]

# model_map = {m[1]: m[0] for m in models}

base_img_width = 300

# is the class a client? or is the class a card constructor?
# i am leaning toward client...
# oh actally the module can be the client and the class the card builder


class Card():
    def __init__(self, deck=None, model=None, tags=[], field1=None, field2=None):
        self.dir = anki_dir
        if deck == None:
            decks = get_decks()
            deck = select(decks)
        if model == None:
            models = get_models()
            model = select(models)
        self.deck = deck
        self.model = model
        self.tags = tags
        mankey_tags = [
            "mankey", pm.now().format("YYYYMMDD-HHmm"),
        ]
        self.tags.extend(mankey_tags)
        if field1:
            self.field1 = format_text(field1)
        else:
            self.field1 = ''
        if field2:
            self.field2 = format_text(field2)
        else:
            self.field2 = ''

    def front(self, front_text):
        self.field1 = format_text(front_text)
        # print(self.field1)
        return self

    def back(self, back_text):
        self.field2 = format_text(back_text)
        # print(self.field2)
        return self

    def tag(self, tag):
        self.tags.append(tag)
        return self

    def tags(self, tags):
        self.tags.extend(tags)
        return self

    def append_img_field1(self, name, url):
        assert "http" in url
        assert " " not in name
        self.field1 += f"\n![{name}]({url})\n"

    def append_img_field2(self, name, url):
        assert "http" in url
        assert " " not in name
        self.field2 += f"\n![{name}]({url})\n"

    def commit(self):
        import anki
        try:
            Collection = anki.storage.Collection
            col = Collection(f"{anki_dir}collection.anki2", log=True)
            m_id = [k for (k, i) in col.models.models.items()
                    if i["name"] == self.model][0]
            col.decks.byName(self.deck)['mid'] = m_id
            note = col.newNote()
            note.model()['did'] = col.decks.byName(self.deck)['id']
            fields = [self.field1, self.field2]
            for f_idx, field in enumerate(fields):
                lines = field.split('\n')
                for idx, ln in enumerate(lines):
                    if ln[:2] == "![":
                        # is image
                        url = ln.split("(")[-1].split(")")[0]
                        name = ln.split("[")[-1].split("]")[0]
                        name = f"{name}.png"
                        name = add_image(url, name, col)
                        lines[idx] = f'<img src="{name}">'
                fields[f_idx] = "\n".join(lines)
            note.fields = fields
            note.tags = col.tags.canonify(
                col.tags.split(
                    ' '.join(self.tags).strip()
                )
            )
            m = note.model()
            m["tags"] = note.tags
            col.models.save(m)
            col.addNote(note)
            col.save()
        finally:
            col.close()
            del col


class Cloze(Card):
    def __init__(self, deck=None, tags=[]):
        super().__init__(deck=deck, model="Cloze", tags=tags)


def select(lis):
    for i, item in enumerate(lis):
        print(f"{i+1}) {item}")
    choice = int(input()) - 1  # input is 1 indexed, convert to 0 index
    return lis[choice]


def template():
    print("""
The weather man says there's
```
    code today 
```

{{c1::a cloze card}} - outside cloze

$ \frac{1}{20,000} \Pi \Delta \sum_{x=0}^3 x^2 $

![imgname](https://.jpg)
    """)


def format_text(text):
    open_pre = 0
    field = text.split('\n')
    for idx, ln in enumerate(field):
        if ln:
            if "```" in ln:
                open_pre ^= 1
                if open_pre:
                    html = "<pre>"
                else:
                    html = "</pre>"
                field[idx] = ln.replace('```', html)
            if ln[0] == "$":
                field[idx] = "[latex]$"+ln.replace('$', '$[/latex]', 2)[9:]
    return '\n'.join(field)


def fetch_img(url):
    res = req.get(url)
    img = PIL_image.open(io.BytesIO(res.content))
    return img


def resize_img(img, shrink=0.5, width=None):
    if width != None:
        width_percent = (width/float(img.size[0]))
        new_height = int(img.size[1]*width_percent)
        return img.resize((width, new_height), PIL_image.ANTIALIAS)
    else:
        return img.resize((int(img.size[0]*shrink), int(img.size[1]*shrink)), PIL_image.ANTIALIAS)


def parse_notes(lns):
    return [n.split('\n') for n in
            '\n'.join(lns).split('---')[1:]]


def add_image(image_url, name, collection):
    """
    take url
    downloads image from url to /tmp
    resizes / scales down if needed
    figure out if png or 
    rename to human_named.png 
    and move to collection.media

    """
    if [i for i in ['JPG', 'jpg'] if i in image_url]:
        ext = 'jpg'
    else:
        ext = "png"

    img = fetch_img(image_url)
    if img.size[0] > base_img_width:
        img = resize_img(img, width=base_img_width)

    img.save(pathlib.Path(anki_dir) / "collection.media" / f"{name}.{ext}")
    return f"{name}.{ext}"


def add_to_anki(doc, col=None):
    lines = doc.split('\n')

    deck = lines[1].strip()
    tags = (
        ['mankey', datetime.datetime.now().strftime("%Y%m%d-%H%M")]
        +
        lines[2].strip().split(' ')
    )

    # print(lines, deck, tags)
    print("-------------------------------------------")
    print(f"Deck: {deck}")

    notes = parse_notes(lines)
    for n in notes:
        print("~note~")
        del n[0]
        model = n[0]
        print(f"Model: {model}")
        if n[1] != '' or '####' not in n[1]:
            n_tags = tags + n[1].split(' ')
            print(f"Tags: {tags}")
            open_pre = 0
            idx = 0
            for ln in n:
                if ln:
                    if "```" in ln:
                        open_pre ^= 1
                        if open_pre:
                            html = "<pre>"
                        else:
                            html = "</pre>"
                        n[idx] = ln.replace('```', html)
                    if ln[:2] == "![":
                        # is image
                        url = ln.split("(")[-1].split(")")[0]
                        print(url)
                        name = ln.split("[")[-1].split("]")[0]
                        print(name)
                        if col:
                            name = add_image(url, name, col)
                        else:
                            name = f"{name}.png"

                        n[idx] = f'<img src="{name}">'
                    if ln[0] == "$":
                        n[idx] = "[latex]$"+ln.replace('$', '$[/latex]', 2)[9:]
                idx += 1

            fields = [''.join(f.split('\n', 1)[1:])
                      for f in '\n'.join(n).split('####')[1:]]
            for i in range(0, len(fields)):
                print(f"Field {i+1}")
                print(fields[i])
        if col:
            m_id = [k for (k, i) in col.models.models.items()
                    if i["name"] == model][0]
            col.decks.byName(deck)['mid'] = m_id
            note = col.newNote()
            note.model()['did'] = col.decks.byName(deck)['id']
            note.fields = fields
            note.tags = col.tags.canonify(
                col.tags.split(
                    ' '.join(n_tags).strip()
                )
            )
            m = note.model()
            m["tags"] = note.tags
            col.models.save(m)
            col.addNote(note)


def print_decks():
    print(get_decks())


def get_decks():
    import anki
    Collection = anki.storage.Collection
    col = Collection(f"{anki_dir}collection.anki2", log=True)
    decks = [d[1]["name"] for d in col.decks.decks.items()]
    col.save()
    col.close()
    del col
    return decks


def print_models():
    print(get_models())


def get_models():
    import anki
    Collection = anki.storage.Collection
    col = Collection(f"{anki_dir}collection.anki2", log=True)
    models = [i['name']for (k, i) in col.models.models.items()]
    col.save()
    col.close()
    del col
    return models


def test_parse(target):
    nb = nbformat.read(target, as_version=4)
    md_cells = [c['source'] for c in nb.cells if c['cell_type']
                == 'markdown' and '## anki\n' in c['source']]
    # return md_cells
    for md in md_cells:
        add_to_anki(md)


def parse(target):
    import anki
    Collection = anki.storage.Collection
    col = Collection(f"{anki_dir}collection.anki2", log=True)
    nb = nbformat.read(target, as_version=4)
    md_cells = [c['source'] for c in nb.cells if c['cell_type']
                == 'markdown' and '## anki\n' in c['source']]
    # return md_cells
    for md in md_cells:
        add_to_anki(md, col)
        break
    col.save()
    col.close()
    del col


def webparse(target):
    nb = nbformat.read(target, as_version=4)
    md_cells = [c['source'] for c in nb.cells if c['cell_type']
                == 'markdown' and '## anki\n' in c['source']]
    # return md_cells
    for md in md_cells:
        add_to_ankiweb(md)
        break


def add_to_ankiweb(md):
    from selenium import webdriver

    driver = webdriver.PhantomJS()

    driver.maximize_window()
    driver.get('https://ankiweb.net/account/login')
    driver.find_element_by_id('email').send_keys(os.environ["ANKIWEB_USER"])
    driver.find_element_by_id('password').send_keys(os.environ["ANKIWEB_PASS"])
    driver.find_element_by_xpath("//input[@value='Log in']").click()

    driver.get("https://ankiuser.net/edit/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Mankey // Parses Anki notes from Jupyter Markdown')
    parser.add_argument("command", type=str, choices=[
                        'parse', 'test', 'decks', 'models', 'template'], )
    parser.add_argument(
        "-f", required=False, type=str, help="path to .md or .ipynb to test parse")
    args = parser.parse_args()
    print(args)
    if args.command == 'test':
        assert args.f != None
        test_parse(args.f)
    elif args.command == 'parse':
        parse(args.f)
    elif args.command == 'decks':
        print_decks()
    elif args.command == 'models':
        print_models()
    elif args.command == "template":
        print("""
# anki
BayesianStatistics
probability math

---
Cloze
note_tag

#### 
The weather man says there's
```
    code today 
```

{{c1::a cloze card}} - outside cloze

$ \frac{1}{20,000} \Pi \Delta \sum_{x=0}^3 x^2 $

![imgname](https://.jpg)


# .

$\displaystyle P( \	ext{forgot, umbrella}) = P( \	ext{rain} ) \	imes P( \	ext{forgot umbrella}) = \frac{1}{10} \	imes \frac{1}{2} = 0.05 $

---
Basic
sum_rule


# field 1

![imgname](https://.jpg)

# field 2

$ \frac{1}{20,000} $
""")
