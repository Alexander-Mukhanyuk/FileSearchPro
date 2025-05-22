import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog # Added simpledialog
from datetime import datetime # For date sorting
import os # For os.path.relpath
# socket, json, tkinter, ttk, messagebox, simpledialog, datetime are already imported.

# --- Discovery Constants ---
DISCOVERY_PORT = 54320
DISCOVERY_BROADCAST_ADDRESS = "<broadcast>" # Or '255.255.255.255'
DISCOVERY_REQUEST_MSG = "DISCOVER_FILESEARCH_SERVER_REQUEST_V1"
DISCOVERY_TIMEOUT = 3.0 # Seconds to wait for responses


# --- Localization (Client) ---
LOC_STRINGS_RU_CLIENT = {
    # ... (existing strings) ...
    "app_title": "LAN File Searcher - Клиент", # Assuming this exists
    "connect_frame_title": "Подключение к серверу", # Assuming this exists
    "server_ip_label": "IP Сервера:", # Assuming this exists
    "server_port_label": "Порт:",
    # connect_button text is part of search_button now, or implied by action
    "search_frame_title": "Параметры поиска",
    "file_mask_label": "Маска файла:",
    "case_sensitive_checkbox": "Учитывать регистр",
    "file_type_label": "Тип файла:",
    "file_type_any": "Любой",
    "file_type_documents": "Документы",
    "file_type_images": "Изображения",
    "file_type_archives": "Архивы",
    "search_button": "Поиск",
    "results_frame_title": "Результаты поиска",
    "tree_col_name": "Имя",
    "tree_col_path": "Путь",
    "tree_col_size": "Размер (байт)",
    "tree_col_modified": "Дата изменения",
    "tree_col_extension": "Расширение",
    # Status messages (could be for a status bar, if implemented)
    "status_connecting": "Подключение к {ip}:{port}...",
    "status_connected": "Подключено к {ip}:{port}",
    "status_connection_failed": "Ошибка подключения: {error}",
    "status_searching": "Поиск...", # Usually implied by disabled button
    "status_search_complete": "Поиск завершен. Найдено {count} файлов.", # For messagebox
    "status_search_failed": "Ошибка поиска: {error}", # For messagebox
    "delete_selected_button": "Удалить выбранные",
    "context_menu_delete_selected": "Удалить выбранные",
    "confirm_delete_title": "Подтверждение удаления",
    "confirm_delete_message": "Вы уверены, что хотите удалить {count} выбранных файла(ов) на сервере? Это действие необратимо.",
    "delete_op_summary_title": "Отчет об удалении",
    "delete_success_message": "Сервер обработал запрос.\nУспешно удалено: {success_count} файл(ов).",
    "delete_error_details": "Ошибки по файлам:\n{details}",
    "error_title": "Ошибка",
    "info_title": "Информация",
    "warning_title": "Предупреждение",
    "no_files_selected_for_delete": "Файлы для удаления не выбраны.",
    "no_valid_paths_for_delete": "Не найдено файлов с корректными путями для удаления.",
    "path_issues_delete_warning_title": "Проблемы с путями",
    "path_issues_delete_warning_message": "Некоторые файлы не могут быть обработаны для удаления из-за проблем с путями (например, не совпадают с ожидаемым корневым каталогом сервера):\n- {problem_paths}\n\nТолько файлы с корректными путями будут отправлены на удаление.",
    "connection_error_ip_port_not_set": "Ошибка подключения: IP адрес или порт сервера не указаны.",
    "input_error_invalid_port": "Ошибка ввода: Неверный номер порта.",
    "config_error_path_column": "Ошибка конфигурации: Колонка 'path' не найдена в настройках Treeview.",
    "failed_to_get_response_from_server": "Не удалось получить ответ от сервера.",
    "server_returned_error": "Сервер вернул ошибку: {error}",
    "unexpected_response_structure": "Неожиданная структура ответа от сервера: {response_str}", # Assuming this exists
    "context_menu_copy_selected_to": "Копировать выбранное в...",
    "prompt_copy_destination_title": "Копировать в папку",
    "prompt_copy_destination_label": "Папка назначения (относительный путь на сервере):", # Simplified label
    "copy_dest_empty_error": "Путь к папке назначения не может быть пустым.",
    "copy_op_status_title": "Статус операции копирования",
    "no_file_selected_for_copy": "Файл для копирования не выбран.",
    "multiple_files_selected_copy_info": "Для копирования через контекстное меню выберите только один файл.",
    "path_conversion_error_copy": "Не удалось преобразовать путь к файлу для операции копирования: {path}",
    "unknown_server_response": "Неизвестный ответ от сервера.", 
    "find_servers_button": "Найти серверы",
    "discovering_servers_title": "Обнаружение серверов",
    "discovering_servers_status": "Отправка запроса на обнаружение...", # For status bar / print
    "discovery_no_servers_found": "Серверы не найдены.",
    "discovery_select_server_title": "Найденные серверы",
    "discovery_response_error": "Ошибка при обработке ответа от сервера {address}: {error}",
    "discovery_sending_request_error": "Ошибка отправки запроса на обнаружение: {error}",
    "discovery_socket_setup_error": "Ошибка настройки сокета для обнаружения: {error}",
    "select_server_prompt": "Выберите сервер из списка:", # For Listbox dialog
    "ok_button": "ОК",
    "status_discovery_finished": "Обнаружение завершено. Найдено {count} серверов.",
}

def tr_cli(key, lang='ru', **kwargs):
    if lang == 'ru':
        return LOC_STRINGS_RU_CLIENT.get(key, f"MISSING_CLI_STRING: {key}").format(**kwargs)
    return f"UNSUPPORTED_LANG_CLI: {key}" # Fallback

# --- Network Client Logic ---
def _connect_socket(server_ip, server_port):
    """Helper to create and connect a socket, with timeout."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10) # 10-second timeout for connection
        client_socket.connect((server_ip, server_port))
        return client_socket
    except socket.timeout:
        # print(f"Connection to {server_ip}:{server_port} timed out.")
        return None
    except socket.error as e:
        # print(f"Socket error connecting to {server_ip}:{server_port}: {e}")
        return None
    # Removed general Exception catch here to be more specific in calling function

def send_request_to_server(server_ip, server_port, request_payload):
    """
    Generic function to send a JSON request to the server and get a JSON response.

    Args:
        server_ip (str): The IP address of the server.
        server_port (int): The port number of the server.
        request_payload (dict): The dictionary to be sent as JSON.

    Returns:
        dict: The parsed JSON response from the server or an error dictionary.
    """
    client_socket = _connect_socket(server_ip, server_port)
    if not client_socket:
        return {"error": f"Failed to connect to {server_ip}:{server_port}. Server might be down or IP/Port is incorrect."}

    response_json_str = "" # Initialize for potential use in error reporting
    try:
        request_json_str = json.dumps(request_payload)
        client_socket.sendall(request_json_str.encode('utf-8'))

        response_bytes = client_socket.recv(40960) # Buffer for response
        if not response_bytes:
            return {"error": "Empty response from server"}
            
        response_json_str = response_bytes.decode('utf-8')
        parsed_response = json.loads(response_json_str)
        return parsed_response

    except socket.timeout:
        return {"error": "Operation timed out."}
    except socket.error as e:
        return {"error": f"Socket error during communication: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"Error decoding JSON response: {e}. Response snippet: {response_json_str[:200]}"}
    except Exception as e: # Catch any other unexpected errors during send/recv
        return {"error": f"An unexpected client error occurred: {e}"}
    finally:
        if client_socket:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except (socket.error, OSError): 
                pass 
            client_socket.close()

def search_files_on_server(server_ip, server_port, search_mask, case_sensitive=False, type_filter="any"):
    """
    Sends a search request to the server using the generic send_request_to_server.
    """
    # The 'path' key is illustrative for the server; the server uses its own fixed_search_directory.
    payload = {
        "command": "search",
        "mask": search_mask,
        "path": "D:/SHARED_FOR_SEARCH", 
        "case_sensitive": case_sensitive,
        "type_filter": type_filter 
    }
    return send_request_to_server(server_ip, server_port, payload)

# --- Tkinter GUI Application ---
class FileSearchClientGUI:
    def __init__(self, master):
        self.master = master
        master.title(tr_cli("app_title"))
        master.geometry("800x600")

        # --- Frames ---
        self.connection_frame = ttk.LabelFrame(master, text=tr_cli("connect_frame_title"), padding="10")
        self.connection_frame.pack(fill="x", padx=10, pady=5)

        self.search_frame = ttk.LabelFrame(master, text=tr_cli("search_frame_title"), padding="10")
        self.search_frame.pack(fill="x", padx=10, pady=5)

        self.results_frame = ttk.LabelFrame(master, text=tr_cli("results_frame_title"), padding="10")
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Initialize Tkinter variables for new widgets
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.type_filter_var = tk.StringVar(value=tr_cli("file_type_any")) # Default value for Combobox

        # Sorting state variables
        self.last_sort_column = None
        self.last_sort_reverse = False

        self.tree_columns = ("name", "path", "size", "modified", "extension")
        # This path is used to attempt to make server paths relative for deletion.
        # It's a simplification; ideally, the server would provide relative paths or a common root.
        self.server_search_root_for_delete = "/tmp/shared_test_folder_server/" # Matches server's fixed_search_directory

        # --- Connection Widgets ---
        self.setup_connection_widgets()
        # --- Search Widgets ---
        self.setup_search_widgets()
        # --- Results Display ---
        self.setup_results_widgets() # This now also sets up context menu and delete button

    def setup_connection_widgets(self):
        ttk.Label(self.connection_frame, text=tr_cli("server_ip_label")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(self.connection_frame, width=30)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(self.connection_frame, text=tr_cli("server_port_label")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.port_entry = ttk.Entry(self.connection_frame, width=10)
        self.port_entry.insert(0, "54321")
        self.port_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        self.find_servers_button = ttk.Button(self.connection_frame, text=tr_cli("find_servers_button"), command=self.discover_and_select_server)
        self.find_servers_button.grid(row=0, column=4, padx=10, pady=5)
        
        self.connection_frame.columnconfigure(1, weight=1) # Allow IP entry to expand
        self.connection_frame.columnconfigure(3, weight=0) # Port entry less expansion
        self.connection_frame.columnconfigure(4, weight=0) # Button less expansion


    def setup_search_widgets(self):
        # Row 0: File Mask
        ttk.Label(self.search_frame, text=tr_cli("file_mask_label")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.mask_entry = ttk.Entry(self.search_frame, width=40) 
        self.mask_entry.insert(0, "*.txt")
        self.mask_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew") 

        # Row 1: Filters
        ttk.Label(self.search_frame, text=tr_cli("file_type_label")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.type_filter_combo = ttk.Combobox(
            self.search_frame, 
            textvariable=self.type_filter_var,
            values=[tr_cli("file_type_any"), tr_cli("file_type_documents"), tr_cli("file_type_images"), tr_cli("file_type_archives")],
            state="readonly",
            width=15
        )
        self.type_filter_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w") 

        self.case_sensitive_check = ttk.Checkbutton(
            self.search_frame, 
            text=tr_cli("case_sensitive_checkbox"), 
            variable=self.case_sensitive_var
        )
        self.case_sensitive_check.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        self.search_button = ttk.Button(self.search_frame, text=tr_cli("search_button"), command=self.perform_search)
        self.search_button.grid(row=0, column=3, rowspan=2, padx=10, pady=5, sticky="ns") # Adjusted column for button

        # Allow column 1 (where entries/combos are) to expand
        self.search_frame.columnconfigure(1, weight=1) # Allow entry/combobox column to expand
        self.search_frame.columnconfigure(3, weight=0) 

        # Context Menu for Treeview
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label=tr_cli("context_menu_delete_selected"), command=self.delete_selected_files)
        self.context_menu.add_command(label=tr_cli("context_menu_copy_selected_to"), command=self.copy_selected_file_to_dialog)


    def setup_results_widgets(self):
        # Frame to hold the treeview and scrollbars
        tree_container = ttk.Frame(self.results_frame)
        tree_container.pack(fill="both", expand=True, pady=(0,5)) # Padding for button below

        self.tree = ttk.Treeview(
            tree_container, 
            columns=self.tree_columns, 
            show="headings", 
            height=15,
            selectmode='extended' # Enable multiple selection
        )
        
        # Setup column headings and sorting commands
        for col_id in self.tree_columns:
            data_type = "str" # Default data_type
            anchor = "w"    # Default anchor to west (left)
                col_text = "" # Will be set by tr_cli
                if col_id == "name": col_text = tr_cli("tree_col_name")
                elif col_id == "path": col_text = tr_cli("tree_col_path")
                elif col_id == "size": 
                    data_type = "int"
                    anchor = "e"
                    col_text = tr_cli("tree_col_size")
                elif col_id == "modified": 
                    data_type = "date"
                    col_text = tr_cli("tree_col_modified")
                elif col_id == "extension": col_text = tr_cli("tree_col_extension")
                else: # Fallback if a new column ID was added to self.tree_columns but not here
                    col_text = col_id.replace("_", " ").title()

            self.tree.heading(col_id, text=col_text, 
                              command=lambda c=col_id, dt=data_type: self.sort_treeview_column(c, dt))
            
            width = 100 
            stretch = tk.NO
            if col_id == "name": width = 150
            elif col_id == "path": 
                width = 300
                stretch = tk.YES # Allow path to stretch
            elif col_id == "size": width = 100
            elif col_id == "modified": width = 150
            elif col_id == "extension": width = 80
            self.tree.column(col_id, width=width, stretch=stretch, anchor=anchor)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        
        # Bind context menu
        self.tree.bind("<Button-3>", self.show_context_menu) # For Windows/Linux right-click
        self.tree.bind("<Button-2>", self.show_context_menu) 

        # "Delete Selected Files" button
        self.delete_button = ttk.Button(self.results_frame, text=tr_cli("delete_selected_button"), command=self.delete_selected_files)
        self.delete_button.pack(pady=5, anchor="se") 

    def show_context_menu(self, event):
        """Shows the context menu on right-click."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            # If the right-clicked item is not part of the current selection,
            # clear the old selection and select just the clicked item.
            if item_id not in self.tree.selection():
                self.tree.selection_set(item_id)
            # Proceed to show context menu only if there's any selection
            if self.tree.selection(): # Check if there's any selection now
                 self.context_menu.tk_popup(event.x_root, event.y_root)
            
    def sort_treeview_column(self, column_id, data_type):
        """Sorts the treeview contents by the clicked column."""
        
        # Retrieve data from treeview for the given column
        # The list comprehension creates a list of tuples, where each tuple is (value, item_id)
        # self.tree.set(item_id, column_id) gets the current value of the 'column_id' for 'item_id'
        data = []
        for item_id in self.tree.get_children(''): # Get all top-level item IDs
            value = self.tree.set(item_id, column_id)
            data.append((value, item_id))

        # Determine sort order
        if self.last_sort_column == column_id:
            self.last_sort_reverse = not self.last_sort_reverse
        else:
            self.last_sort_reverse = False
        self.last_sort_column = column_id

        # Define sort key based on data_type
        key_func = None
        if data_type == "int":
            def to_int_safe(x):
                try:
                    return int(x[0]) # x[0] is the value, x[1] is item_id
                except (ValueError, TypeError):
                    return 0 # Default for non-convertible values
            key_func = to_int_safe
        elif data_type == "date":
            def to_datetime_safe(x):
                try:
                    # Assuming ISO format from server: YYYY-MM-DDTHH:MM:SS.microseconds
                    # Or YYYY-MM-DDTHH:MM:SS if microseconds are not always there
                    dt_str = x[0]
                    if '.' in dt_str: # handles microseconds
                        return datetime.fromisoformat(dt_str.split('.')[0])
                    return datetime.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    return datetime.min # Default for non-convertible/missing dates
            key_func = to_datetime_safe
        else: # "str" or any other type
            key_func = lambda x: str(x[0]).lower() # Case-insensitive string sort

        data.sort(key=key_func, reverse=self.last_sort_reverse)

        # Repopulate treeview
        for index, (_, item_id) in enumerate(data): # value is not needed here, only item_id
            self.tree.move(item_id, '', index) # Move item_id to the new 'index' position

        # Optional: Update header visuals (e.g., add ▲/▼).
        # This is a more advanced step and can be added later.
        # For now, it just sorts without visual indication in the header beyond the data changing.
        # This requires managing original header texts to avoid appending multiple arrows.
        # For now, just update the display of the current column being sorted.
        for col in self.tree_columns: # Clear previous arrows from other columns
             current_text = self.tree.heading(col, 'text')
             current_text = current_text.replace(' ▲', '').replace(' ▼', '')
             self.tree.heading(col, text=current_text)
        
        new_header_text = self.tree.heading(column_id, 'text').replace(' ▲', '').replace(' ▼', '')
        new_header_text += ' ▲' if not self.last_sort_reverse else ' ▼' 
        self.tree.heading(column_id, text=new_header_text)

    def copy_selected_file_to_dialog(self):
        selected_ids = self.tree.selection()

        if not selected_ids:
            messagebox.showinfo(tr_cli("info_title"), tr_cli("no_file_selected_for_copy"))
            return
        
        if len(selected_ids) > 1:
            messagebox.showinfo(tr_cli("info_title"), tr_cli("multiple_files_selected_copy_info"))
            # We could choose to operate on self.tree.focus() which is the item with current focus
            # For now, let's just take the first one if user insists or simplify to single selection for context menu.
            # The subtask says "focus on a single selected file from the context menu".
            # If show_context_menu ensures only one item is effectively 'targeted', this check might be redundant
            # or could be a safeguard. Let's assume show_context_menu has set focus appropriately.
            item_id = self.tree.focus() # Get the item that has focus (likely the one right-clicked)
            if not item_id or item_id not in selected_ids: # Fallback if focus is weird or not in selection
                 item_id = selected_ids[0]
        else:
            item_id = selected_ids[0]

        try:
            source_full_path = self.tree.item(item_id, 'values')[self.tree_columns.index('path')]
        except (IndexError, ValueError):
            messagebox.showerror(tr_cli("error_title"), tr_cli("config_error_path_column"))
            return

        source_relative_path = ""
        if source_full_path.startswith(self.server_search_root_for_delete):
            # Ensure server_search_root_for_delete ends with a separator for clean relpath
            root_path_for_relpath = os.path.join(self.server_search_root_for_delete, "") 
            source_relative_path = os.path.relpath(source_full_path, root_path_for_relpath)
            source_relative_path = source_relative_path.replace("\\", "/") # Ensure forward slashes
        else:
            messagebox.showerror(tr_cli("error_title"), tr_cli("path_conversion_error_copy", path=source_full_path))
            return

        dest_relative_folder = simpledialog.askstring(
            tr_cli("prompt_copy_destination_title"),
            tr_cli("prompt_copy_destination_label"),
            parent=self.master 
        )

        if not dest_relative_folder: # User cancelled or entered empty string
            if dest_relative_folder == "": # Explicitly empty
                 messagebox.showerror(tr_cli("error_title"), tr_cli("copy_dest_empty_error"))
            return # Cancelled returns None, so this handles both

        ip = self.ip_entry.get()
        port_str = self.port_entry.get()
        if not ip or not port_str:
            messagebox.showerror(tr_cli("error_title"), tr_cli("connection_error_ip_port_not_set"))
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror(tr_cli("error_title"), tr_cli("input_error_invalid_port"))
            return

        payload = {
            "command": "copy", 
            "source_path": source_relative_path, 
            "destination_folder": dest_relative_folder
        }
        
        # Disable buttons during operation
        current_search_state = self.search_button.cget('state')
        current_delete_state = self.delete_button.cget('state')
        self.search_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)

        response = send_request_to_server(ip, port, payload)

        # Re-enable buttons to their previous state (if they were already disabled for other reasons)
        self.search_button.config(state=current_search_state)
        self.delete_button.config(state=current_delete_state)

        status_title = tr_cli("copy_op_status_title")
        if response and "error" not in response and response.get("status") == "success":
            messagebox.showinfo(status_title, response.get("message", tr_cli("file_copied_successfully", source_filename=os.path.basename(source_relative_path), dest_folder=dest_relative_folder))) # Provide default success if message missing
            self.perform_search() # Refresh view
        elif response and "message" in response: # Server sent a specific error message in its known structure
            messagebox.showerror(status_title, response["message"])
        elif response and "error" in response: # Error from send_request_to_server (e.g. connection)
             messagebox.showerror(status_title, response["error"])
        else:
            messagebox.showerror(status_title, tr_cli("unknown_server_response"))


    def delete_selected_files(self):
        selected_item_ids = self.tree.selection()
        if not selected_item_ids:
            messagebox.showinfo(tr_cli("info_title"), tr_cli("no_files_selected_for_delete"))
            return

        try:
            path_column_index = self.tree_columns.index("path")
        except ValueError:
            messagebox.showerror(tr_cli("error_title"), tr_cli("config_error_path_column"))
            return

        files_to_request_delete = []
        problematic_paths_details = [] # To store details of paths that couldn't be processed

        for item_id in selected_item_ids:
            item_values = self.tree.item(item_id, 'values')
            if len(item_values) > path_column_index:
                full_path_on_client = item_values[path_column_index]
                if full_path_on_client.startswith(self.server_search_root_for_delete):
                    relative_path = full_path_on_client[len(self.server_search_root_for_delete):]
                    # Normalize path separators for cross-platform consistency if needed, though server should handle it.
                    files_to_request_delete.append(relative_path.replace("\\", "/")) 
                else:
                    problematic_paths_details.append(f"'{full_path_on_client}' (does not match expected server root: {self.server_search_root_for_delete})")
            else:
                problematic_paths_details.append(f"Item ID '{item_id}' has insufficient values to get path.")


        if problematic_paths_details:
            messagebox.showwarning(
                tr_cli("warning_title"), 
                tr_cli("path_issues_delete_warning_message", problem_paths="\n- ".join(problematic_paths_details))
            )

        if not files_to_request_delete:
            messagebox.showinfo(tr_cli("info_title"), tr_cli("no_valid_paths_for_delete"))
            return

        confirmed = messagebox.askyesno(
            tr_cli("confirm_delete_title"), 
            tr_cli("confirm_delete_message", count=len(files_to_request_delete)) + 
            "\n\n" + "\n- ".join(files_to_request_delete)
        )
        if not confirmed:
            return

        ip = self.ip_entry.get()
        port_str = self.port_entry.get()
        if not ip or not port_str:
            messagebox.showerror(tr_cli("error_title"), tr_cli("connection_error_ip_port_not_set"))
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror(tr_cli("error_title"), tr_cli("input_error_invalid_port"))
            return

        delete_payload = { "command": "delete", "files": files_to_request_delete }
        
        self.delete_button.config(state=tk.DISABLED)
        self.search_button.config(state=tk.DISABLED) 
        
        # messagebox.showinfo(tr_cli("info_title"), tr_cli("status_connecting", ip=ip, port=port)) 
        response = send_request_to_server(ip, port, delete_payload)
        
        self.delete_button.config(state=tk.NORMAL)
        self.search_button.config(state=tk.NORMAL)

        deleted_count = 0
        error_details_list = []

        if response and response.get("status") == "success" and "results" in response:
            for result in response["results"]:
                if result.get("status") == "deleted":
                    deleted_count += 1
                else:
                    error_details_list.append(f"- {result.get('file', 'Unknown file')}: {result.get('message', 'Unknown error')}")
            
            summary_msg = tr_cli("delete_success_message", success_count=deleted_count)
            if error_details_list:
                summary_msg += "\n\n" + tr_cli("delete_error_details", details="\n".join(error_details_list))
            messagebox.showinfo(tr_cli("delete_op_summary_title"), summary_msg)
            
            self.perform_search() 
            
        elif response and "error" in response:
            messagebox.showerror(tr_cli("error_title"), tr_cli("server_returned_error", error=response['error']))
        else:
            messagebox.showerror(tr_cli("error_title"), tr_cli("failed_to_get_response_from_server"))

    def _update_status(self, message): # Placeholder for actual status bar
        print(f"Status: {message}")

    def discover_and_select_server(self):
        self._update_status(tr_cli("discovering_servers_status"))
        
        # Disable buttons during discovery
        self.find_servers_button.config(state=tk.DISABLED)
        original_search_state = self.search_button.cget('state')
        original_delete_state = self.delete_button.cget('state')
        original_copy_state = self.context_menu.entrycget(1, "state") # Assuming copy is index 1

        self.search_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.context_menu.entryconfig(tr_cli("context_menu_copy_selected_to"), state=tk.DISABLED)


        discovered_servers = self._discover_servers_network_task()

        # Re-enable buttons
        self.find_servers_button.config(state=tk.NORMAL)
        self.search_button.config(state=original_search_state) 
        self.delete_button.config(state=original_delete_state)
        self.context_menu.entryconfig(tr_cli("context_menu_copy_selected_to"), state=original_copy_state)


        self._update_status(tr_cli("status_discovery_finished", count=len(discovered_servers)))

        if not discovered_servers:
            messagebox.showinfo(tr_cli("discovering_servers_title"), tr_cli("discovery_no_servers_found"))
        else:
            self._show_server_selection_dialog(discovered_servers)

    def _discover_servers_network_task(self):
        discovered_servers = []
        active_ips_ports = set() 

        try:
            discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discover_sock.settimeout(DISCOVERY_TIMEOUT)
        except socket.error as e:
            messagebox.showerror(tr_cli("discovering_servers_title"), tr_cli("discovery_socket_setup_error", error=str(e)))
            return []

        try:
            discover_sock.sendto(DISCOVERY_REQUEST_MSG.encode('utf-8'), (DISCOVERY_BROADCAST_ADDRESS, DISCOVERY_PORT))
        except Exception as e:
            messagebox.showerror(tr_cli("discovering_servers_title"), tr_cli("discovery_sending_request_error", error=str(e)))
            discover_sock.close()
            return []

        while True:
            try:
                response, addr = discover_sock.recvfrom(1024)
                response_str = response.decode('utf-8')
                
                server_data = json.loads(response_str)
                server_name = server_data.get("server_name")
                service_port = server_data.get("service_port")
                protocol_version = server_data.get("protocol_version")
                server_ip = addr[0]

                if server_name and service_port: 
                    server_key = (server_ip, service_port)
                    if server_key not in active_ips_ports:
                        discovered_servers.append({
                            "name": server_name, 
                            "ip": server_ip, 
                            "port": service_port, 
                            "version": protocol_version
                        })
                        active_ips_ports.add(server_key)
            except socket.timeout:
                break 
            except json.JSONDecodeError as e:
                self._update_status(tr_cli("discovery_response_error", address=addr, error=str(e))) # To status bar
            except Exception as e: 
                self._update_status(tr_cli("discovery_response_error", address=addr, error=str(e))) # To status bar
        
        discover_sock.close()
        return discovered_servers

    def _show_server_selection_dialog(self, servers_list):
        dialog = tk.Toplevel(self.master)
        dialog.title(tr_cli("discovery_select_server_title"))
        dialog.geometry("450x300") # Adjusted size
        dialog.transient(self.master) 
        dialog.grab_set() 

        ttk.Label(dialog, text=tr_cli("select_server_prompt")).pack(pady=(10,5))

        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        listbox = tk.Listbox(listbox_frame, height=10, exportselection=False)
        listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        for server in servers_list: # Removed enumerate as idx not needed directly for insert
            listbox.insert(tk.END, f"{server['name']} ({server['ip']}:{server['port']}) - v{server.get('version', 'N/A')}")

        def on_select_action():
            try:
                idx = listbox.curselection()[0]
                selected_server = servers_list[idx]
                self.ip_entry.delete(0, tk.END)
                self.ip_entry.insert(0, selected_server["ip"])
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, str(selected_server["port"]))
                dialog.destroy()
            except IndexError: 
                pass 
        
        listbox.bind("<Double-1>", lambda e: on_select_action())
        
        button_frame = ttk.Frame(dialog) # Frame for buttons
        button_frame.pack(pady=10)

        ok_button = ttk.Button(button_frame, text=tr_cli("ok_button"), command=on_select_action)
        ok_button.pack(side="left", padx=5)
        
        cancel_button = ttk.Button(button_frame, text=tr_cli("cancel_button", default_text="Cancel"), command=dialog.destroy) # Added cancel
        cancel_button.pack(side="left", padx=5)


        dialog.update_idletasks() 
        master_x = self.master.winfo_x()
        master_y = self.master.winfo_y()
        master_width = self.master.winfo_width()
        master_height = self.master.winfo_height()
        dialog_width = dialog.winfo_width()
        dialog_height = dialog.winfo_height()
        x_offset = (master_width - dialog_width) // 2
        y_offset = (master_height - dialog_height) // 2
        dialog.geometry(f"+{master_x + x_offset}+{master_y + y_offset}")
        
        dialog.wait_window() 


    def perform_search(self):
        # Clear previous results
        for i in self.tree.get_children():
            self.tree.delete(i)

        ip = self.ip_entry.get()
        port_str = self.port_entry.get()
        mask = self.mask_entry.get()
        
        # Get values from new filter widgets
        case_sensitive = self.case_sensitive_var.get()
        # Map display name from combobox back to key for server (e.g. "Любой" -> "any")
        type_filter_display = self.type_filter_var.get()
        type_filter_map = {
            tr_cli("file_type_any"): "any",
            tr_cli("file_type_documents"): "documents",
            tr_cli("file_type_images"): "images",
            tr_cli("file_type_archives"): "archives",
        }
        type_filter = type_filter_map.get(type_filter_display, "any")


        if not ip:
            messagebox.showerror(tr_cli("error_title"), tr_cli("connection_error_ip_port_not_set")) # Example, needs specific msg
            return
        if not port_str:
            messagebox.showerror(tr_cli("error_title"), tr_cli("connection_error_ip_port_not_set")) # Example, needs specific msg
            return
        if not mask:
            messagebox.showerror(tr_cli("error_title"), "File mask cannot be empty.") # TODO: Add to LOC_STRINGS
            return
        
        try:
            port = int(port_str)
            if not (0 < port < 65536):
                 raise ValueError("Port number out of range.")
        except ValueError:
            messagebox.showerror(tr_cli("error_title"), tr_cli("input_error_invalid_port"))
            return

        self.search_button.config(state=tk.DISABLED) 
        self.delete_button.config(state=tk.DISABLED) # Disable delete during search too
        
        # messagebox.showinfo(tr_cli("info_title"), tr_cli("status_searching")) # Optional status
        response = search_files_on_server(ip, port, mask, case_sensitive, type_filter)
        
        self.search_button.config(state=tk.NORMAL) 
        self.delete_button.config(state=tk.NORMAL)

        if response is None: 
             messagebox.showerror(tr_cli("error_title"), tr_cli("failed_to_get_response_from_server"))
             return

        if "error" in response:
            messagebox.showerror(tr_cli("error_title"), tr_cli("server_returned_error", error=response['error']))
        elif "results" in response and isinstance(response["results"], list):
            file_list = response["results"]
            if not file_list:
                messagebox.showinfo(tr_cli("info_title"), tr_cli("status_search_complete", count=0))
            else:
                for file_info in file_list:
                    self.tree.insert("", tk.END, values=(
                        file_info.get("name", ""),
                        file_info.get("path", ""),
                        file_info.get("size", ""),
                        file_info.get("modified_date", ""),
                        file_info.get("extension", "")
                    ))
        else:
            messagebox.showerror("Error", f"Unexpected response from server: {str(response)[:200]}")


if __name__ == '__main__':
    # --- Previous command-line test calls (now commented out) ---
    # server_ip = "127.0.0.1"
    # server_port = 54321 
    # print("--- Client: Testing File Search ---")
    # search_mask_txt = "*.txt"
    # print(f"\nAttempting to search for: '{search_mask_txt}'")
    # results = search_files_on_server(server_ip, server_port, search_mask_txt)
    # ... (rest of the old test code) ...
    # print("\n--- Client: Test Complete ---")

    root = tk.Tk()
    app = FileSearchClientGUI(root)
    root.mainloop()
