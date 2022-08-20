# Browser for Markdown Pages
# Thomas Führinger, 2022, https://github.com/thomasfuhringer/MarkdownPage

import tymber as ty # https://github.com/thomasfuhringer/tymber
import pickle, zipfile, os, shutil, pathlib, socket, io, sys, webbrowser

#default_host = "localhost"
default_host = "45.76.133.182"
default_port = 1550
#identifier = bytes([0x06, 0x0E])
run_code = False

def send(socket, data):
    length = len(data)
    socket.send(length.to_bytes(4, byteorder="big"))
    socket.sendall(data)

def receive(socket):
    length_raw = socket.recv(4)
    if len(length_raw) != 4:
        return None
    length = int.from_bytes(length_raw, byteorder="big")
    data = bytearray(length)
    view = memoryview(data)
    next_offset = 0
    while length - next_offset > 0:
        recv_size = socket.recv_into(view[next_offset:], length - next_offset)
        if recv_size == 0:
            return None
        next_offset += recv_size
    return data

def query(host, path, port=default_port):
    open_socket = socket.socket()
    try:
        open_socket.connect((host, port))
        if path is not None and path != "":
            path_bytes = bytes(path, "utf-8")
            query_bytes = bytes([0x06, 0x0E, 0]) + len(path_bytes).to_bytes(2, byteorder="big") + path_bytes
        else:
            query_bytes = bytes([0x06, 0x0E, 0, 0, 0])
        send(open_socket, query_bytes)
    except Exception: # (ConnectionRefusedError) as e
        status_bar.set_text("Remote server not responding")
        return None

    answer = receive(open_socket)

    if answer[:2] != bytes([0x06, 0x0E]): # identifier
        status_bar.set_text("Invalid server")
        return None
    open_socket.close()
    return answer[3:]

def get_page(address):
    global page_open, page_open_name
    separator = address.find("/")
    if  separator == -1:
        host = address
        path = ""
    else:
        host = address[:separator]
        path = address[separator + 1:]

    answer = query(host, path)
    if not answer:
        return False

    if answer[0:1] == b"4":
        path_lenght = int.from_bytes(answer[1: 3], byteorder='big')
        path = answer[3 : 3 + path_lenght].decode("utf-8")
        status_bar.set_text("Page not found: " + host + "/" + path)
        return False

    page_length = int.from_bytes(answer[1:5], byteorder='big')
    page = answer[5:page_length + 5]

    clear_directory(tmp_directory)
    with zipfile.ZipFile(io.BytesIO(page), mode="r") as archive:
        archive.extractall(tmp_directory)

    pos = page_length + 5
    path_lenght = int.from_bytes(answer[pos: pos + 2], byteorder='big')
    path = answer[pos + 2 : pos + 2 + path_lenght].decode("utf-8")

    pos += path_lenght + 2
    subdirectory_count = int.from_bytes(answer[pos: pos + 2], byteorder='big')
    subdirectories = []
    pos += 2
    for index in range(subdirectory_count):
        subdirectory_length = int.from_bytes(answer[pos: pos + 2], byteorder='big')
        subdirectory = answer[pos + 2:pos + 2 + subdirectory_length]
        pos += subdirectory_length + 6
        subdirectories.append(subdirectory.decode("utf-8"))

    text = pathlib.Path(os.path.join(tmp_directory, "Text.md")).read_text(encoding="utf-8")
    text_view.data = (text, tmp_directory)
    if path == "":
        entry_path.data = host
        set_window_caption(host)
        button_up.enabled = False
        menu_item_navigate_up.enabled = False
    else:
        entry_path.data = host + "/" + path
        separator = path.find("/")
        if  separator == -1:
            page_open_name = path
        else:
            page_open_name = path[separator + 1:]
        set_window_caption(page_open_name)
        button_up.enabled = True
        menu_item_navigate_up.enabled = True

    listview_subpage.data = None
    subpage_list.clear()
    for subdirectory in subdirectories:
        subpage_list.append([subdirectory])
    listview_subpage.data = subpage_list

    attachments_listview.data = None
    attachments_list.clear()
    with os.scandir(tmp_directory) as iterator:
        for entry in iterator:
            if entry.is_file() and entry.name not in ["Text.md", "Data.yml", "Code.py", "Code.pyd"]:
                attachments_list.append([entry.name])
    attachments_listview.data = attachments_list

    page_open = page
    status_bar.set_text(None)

    execute_code()

    return True

def save_state():
    position = ty.app.window.position
    ty.set_setting("MakrDownPage", "Browser", "WindowPos", pickle.dumps(position))
    ty.set_setting("MakrDownPage", "Browser", "SplitterH", pickle.dumps(splitter_horizontal.position))
    ty.set_setting("MakrDownPage", "Browser", "SplitterV", pickle.dumps(splitter_vertical.position))

def load_state():
    pos_bytes = ty.get_setting("MakrDownPage", "Browser", "WindowPos")
    splitter_h_bytes = ty.get_setting("MakrDownPage", "Browser", "SplitterH")
    splitter_v_bytes = ty.get_setting("MakrDownPage", "Browser", "SplitterV")
    if pos_bytes is not None:
        ty.app.window.position = pickle.loads(pos_bytes)
    if splitter_h_bytes is not None:
        splitter_horizontal.position = pickle.loads(splitter_h_bytes)
    if splitter_v_bytes is not None:
        splitter_vertical.position = pickle.loads(splitter_v_bytes)

def window__before_close(self):
    save_state()
    return True

def clear_directory(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))

def open_page(file_name):
    clear_directory(tmp_directory)

    with zipfile.ZipFile(file_name, mode="r") as archive:
        archive.extractall(tmp_directory)

    text = pathlib.Path(os.path.join(tmp_directory, "Text.md")).read_text(encoding="utf-8")
    text_view.data = (text, tmp_directory)
    set_window_caption(file_name)

    listview_subpage.data = None
    subpage_list.clear()

    attachments_listview.data = None
    attachments_list.clear()
    with os.scandir(tmp_directory) as iterator:
        for entry in iterator:
            if entry.is_file() and entry.name not in ["Text.md", "Data.yml", "Code.py", "Code.pyd"]:
                attachments_list.append([entry.name])
    attachments_listview.data = attachments_list

    entry_path.data = None
    global page_open
    page_open = file_name
    button_up.enabled = False
    menu_item_navigate_up.enabled = False
    execute_code()

def set_window_caption(string):
    if string :
        app.window.caption = string + " - Markdown Page"
    else:
        app.window.caption = "Markdown Page"

def set_navigation_stack(address):
    global navigation_stack
    global navigation_stack_index
    navigation_stack = navigation_stack[:navigation_stack_index + 1]
    navigation_stack.append(address)
    navigation_stack_index += 1
    if navigation_stack_index > 0:
        button_back.enabled = True
        menu_item_navigate_back.enabled = True
    if navigation_stack_index > 0:
        button_forward.enabled = False
        menu_item_navigate_forward.enabled = False

def menu_item_file_open__on_click():
    selector = ty.FileSelector("Open file", extension="mdp")
    file_name = selector.run()
    if file_name:
        open_page(file_name)

def menu_item_file_save__on_click():
    if page_open == None:
        return
    selector = ty.FileSelector("Save As", base_directory, page_open_name, extension="mdp", save = True)
    file_name = selector.run()
    if file_name:
        with open(file_name, "wb") as file:
            file.write(page_open)
        status_bar.set_text("Page saved as '" + file_name + "'")

def menu_item_file_close__on_click():
    text_view.data = (" ", tmp_directory)
    set_window_caption(None)
    page_open = None
    listview_subpage.data = None
    attachments_listview.data = None

def menu_item_navigate_up__on_click():
    address = entry_path.data
    separator = address.rfind("/")
    if  separator == -1:
        return

    address = address[:separator]
    separator = address.find("/")
    if  separator == -1:
        host = address
        path = ""
    else:
        host = address[:separator]
        path = address[separator + 1:]

    if get_page(address):
        set_navigation_stack(address)

def menu_item_navigate_back__on_click():
    global navigation_stack_index
    if navigation_stack_index > 0:
        navigation_stack_index -= 1
        if get_page(navigation_stack[navigation_stack_index]):
            button_back.enabled = True if navigation_stack_index > 0 else False
            menu_item_navigate_back.enabled = True if navigation_stack_index > 0 else False
            button_forward.enabled = True
            menu_item_navigate_forward.enabled = True

def menu_item_navigate_forward__on_click():
    global navigation_stack_index
    if len(navigation_stack) > navigation_stack_index + 1:
        navigation_stack_index += 1
        if get_page(navigation_stack[navigation_stack_index]):
            button_back.enabled = True
            menu_item_navigate_back.enabled = True
            button_forward.enabled = True if len(navigation_stack) > navigation_stack_index + 1 else False
            menu_item_navigate_forward.enabled = True if len(navigation_stack) > navigation_stack_index + 1 else False

def menu_item_about__on_click():
    window = ty.Window("About Markdown Page", width = 320, height = 240)
    window.icon = icon
    ty.Label(window, "1", 40, 50, -40, 22, "By Thomas Führinger, 2022")
    ty.Label(window, "2", 40, 70, -40, 22, "https://github.com/thomasfuhringer/MarkdownPage")
    ty.Label(window, "3", 40, 90, -40, 22, "Version 0.1")

    window.run()

def button_get__on_click(self):
    address = entry_path.input_string
    if get_page(address):
        set_navigation_stack(address)

def entry_path__on_key(key, widget):
    if key == ty.Key.enter:
        button_get__on_click(None)

def button_up__on_click(self):
    menu_item_navigate_up__on_click()

def button_back__on_click(self):
    menu_item_navigate_back__on_click()

def button_forward__on_click(self):
    menu_item_navigate_forward__on_click()

def listview_subpage__on_row_canged(self):
    if entry_path.data[-1:] == "/":
        address = entry_path.data + subpage_list[self.row][0]
    else:
        address = entry_path.data + "/" + subpage_list[self.row][0]

    if get_page(address):
        set_navigation_stack(address)

def attachments_listview__on_double_click(self, row):
    selector = ty.FileSelector("Save As", name=attachments_list[row][0], extension="mdp", save = True)
    file_name = selector.run()
    if file_name:
        shutil.copy2(os.path.join(tmp_directory, attachments_list[row][0]), file_name)
        status_bar.set_text("Attachment saved as '" + file_name + "'")

def text_view__on_click_link(self, link):
    if link[:4] == "http" or link[:5] == "https":
        webbrowser.open(link, new=2)
    else:
        if link[:1] == "/":
            address = entry_path.data
            separator = address.find("/")
            if  separator == -1:
                return
            entry_path.data = address[:separator] + link
        elif link[:2] == "./":
            entry_path.data += link[1:]
        elif link[:3] == "../":
            address = entry_path.data
            separator = address.rfind("/")
            if  separator == -1:
                return
            entry_path.data = address[:separator] + link[2:]
        else:
            entry_path.data = link
        button_get__on_click(None)

def execute_code():
    if run_code and os.path.exists(tmp_directory + "\Code.py"):
        import Code
        Code.main()

app = ty.Application(ty.Window("Markdown Page", width=740, height=580))
app.window.before_close = window__before_close
icon = ty.Icon("Mdp.ico")
app.window.icon = icon
status_bar = ty.StatusBar(app.window, [])

menu = ty.Menu(app, "main", "Main")
menu_file = ty.Menu(menu, "file", "&File")
menu_item_file_open = ty.MenuItem(menu_file, "open", "&Open\tCtrl+O", menu_item_file_open__on_click, ty.Icon(ty.StockIcon.file_open))
menu_item_file_save = ty.MenuItem(menu_file, "save", "&Save As..\tCtrl+S", menu_item_file_save__on_click)
menu_item_file_close = ty.MenuItem(menu_file, "close", "&Close\tCtrl+O", menu_item_file_close__on_click)
menu_navigate = ty.Menu(menu, "navigate", "&Navigate")
menu_item_navigate_up = ty.MenuItem(menu_navigate, "up", "&Up", menu_item_navigate_up__on_click)
menu_item_navigate_back = ty.MenuItem(menu_navigate, "back", "&Back", menu_item_navigate_back__on_click)
menu_item_navigate_forward = ty.MenuItem(menu_navigate, "forward", "&Forward", menu_item_navigate_forward__on_click)
menu_help = ty.Menu(menu, "help", "&Help")
menu_item_about = ty.MenuItem(menu_help, "about", "&About...", menu_item_about__on_click, ty.Icon(ty.StockIcon.information))
""""
tool_bar = ty.ToolBar(app.window)
tool_bar.append_item(menu_item_file_open)
"""
label_path = ty.Label(app.window, "path_label", 5, 5, 36, 22, "Online")
entry_path = ty.Entry(app.window, "path", 42, 5, -50, 22, default_host)
entry_path.on_key = entry_path__on_key
button_get = ty.Button(app.window, "run", -40, 5, -5, 22, "Get")
button_get.on_click = button_get__on_click

splitter_vertical = ty.Splitter(app.window, "splitter_vertical", 5, 32, -5, -5)
splitter_vertical.position = 176
splitter_horizontal = ty.Splitter(splitter_vertical.box1, "splitter_vertical", 0, 0, 0, 0)
splitter_horizontal.position = -120
splitter_horizontal.vertical = False

button_up = ty.Button(splitter_horizontal.box1, "up", -22, 0, 22, 22, "▲")
button_up.on_click = button_up__on_click
button_up.enabled = False
menu_item_navigate_up.enabled = False
button_back = ty.Button(splitter_horizontal.box1, "back", 0, 0, 22, 22, "◀")
button_back.on_click = button_back__on_click
button_back.enabled = False
menu_item_navigate_back.enabled = False
button_forward = ty.Button(splitter_horizontal.box1, "forward", 25, 0, 22, 22, "▶")
button_forward.on_click = button_forward__on_click
button_forward.enabled = False
menu_item_navigate_forward.enabled = False

listview_subpage = ty.ListView(splitter_horizontal.box1, "listview_subpage", 0, 30, 0, -2)
listview_subpage.columns = [["Sub Pages", str, 170]]
listview_subpage.on_selection_changed = listview_subpage__on_row_canged

attachments_listview = ty.ListView(splitter_horizontal.box2, "attachments_listview", 0, 0, 0, 0)
attachments_listview.columns = [["Attachments", str, 170]]
attachments_listview.on_double_click = attachments_listview__on_double_click

text_view =ty.TextView(splitter_vertical.box2, "text_view", 0, 0, 0, 0)
text_view.margin = 20
text_view.on_click_link = text_view__on_click_link

load_state()

base_directory = os.path.abspath(os.path.dirname(__file__))
tmp_directory = os.path.join(base_directory, "tmp")
sys.path.append(tmp_directory)
subpage_list = []
attachments_list = []
navigation_stack = []
navigation_stack_index = -1
page_open = None
page_open_name = None

if len(sys.argv) > 1:
    address = sys.argv[1]
    if address[-4:].lower() == ".mdp":
        open_page(address)
    else:
        entry_path.data = address
        button_get__on_click(None)

app.run()
