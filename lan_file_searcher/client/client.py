import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime # For date sorting

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
        master.title("LAN File Searcher Client")
        master.geometry("800x600")

        # --- Frames ---
        self.connection_frame = ttk.LabelFrame(master, text="Connection Details", padding="10")
        self.connection_frame.pack(fill="x", padx=10, pady=5)

        self.search_frame = ttk.LabelFrame(master, text="Search Criteria", padding="10")
        self.search_frame.pack(fill="x", padx=10, pady=5)

        self.results_frame = ttk.LabelFrame(master, text="Search Results", padding="10")
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Initialize Tkinter variables for new widgets
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.type_filter_var = tk.StringVar(value="Any")

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
        self.setup_results_widgets()

    def setup_connection_widgets(self):
        ttk.Label(self.connection_frame, text="Server IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(self.connection_frame, width=30)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.connection_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.port_entry = ttk.Entry(self.connection_frame, width=10)
        self.port_entry.insert(0, "54321")
        self.port_entry.grid(row=0, column=3, padx=5, pady=5)

    def setup_search_widgets(self):
        # Row 0: File Mask
        ttk.Label(self.search_frame, text="File Mask:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.mask_entry = ttk.Entry(self.search_frame, width=40) # Made wider
        self.mask_entry.insert(0, "*.txt")
        self.mask_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew") # Use ew for expansion

        # Row 1: Filters
        ttk.Label(self.search_frame, text="File Type:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.type_filter_combo = ttk.Combobox(
            self.search_frame, 
            textvariable=self.type_filter_var,
            values=["Any", "Documents", "Images", "Archives"],
            state="readonly",
            width=15
        )
        self.type_filter_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w") # Align left

        self.case_sensitive_check = ttk.Checkbutton(
            self.search_frame, 
            text="Case Sensitive", 
            variable=self.case_sensitive_var
        )
        self.case_sensitive_check.grid(row=1, column=2, padx=5, pady=5, sticky="w")


        # Search button moved to span across more columns or be at the end
        self.search_button = ttk.Button(self.search_frame, text="Search", command=self.perform_search)
        self.search_button.grid(row=0, column=2, rowspan=2, padx=10, pady=5, sticky="ns") # Span rows, stick N-S

        # Allow column 1 (where entries/combos are) to expand
        self.search_frame.columnconfigure(1, weight=1)

        # Context Menu for Treeview
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Delete Selected", command=self.delete_selected_files)


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
            col_text = col_id.replace("_", " ").title() # Default column text

            if col_id == "size":
                data_type = "int"
                anchor = "e" # Right align size
                col_text = "Size (Bytes)"
            elif col_id == "modified":
                data_type = "date"
                col_text = "Date Modified"
            elif col_id == "name":
                col_text = "File Name"
            elif col_id == "path":
                col_text = "Full Path"
            elif col_id == "extension":
                col_text = "Extension"
            
            self.tree.heading(col_id, text=col_text, 
                              command=lambda c=col_id, dt=data_type: self.sort_treeview_column(c, dt))
            
            # Setup column widths and stretch properties
            width = 100 # Default width
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
        self.tree.bind("<Button-2>", self.show_context_menu) # For macOS right-click

        # "Delete Selected Files" button
        self.delete_button = ttk.Button(self.results_frame, text="Delete Selected Files", command=self.delete_selected_files)
        self.delete_button.pack(pady=5, anchor="se") # Anchor to the south-east (bottom-right)

    def show_context_menu(self, event):
        """Shows the context menu on right-click if an item is under the cursor."""
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
        new_header_text += ' ▲' if not self.last_sort_reverse else ' ▼' # Add new arrow
        self.tree.heading(column_id, text=new_header_text)

    def delete_selected_files(self):
        selected_item_ids = self.tree.selection()
        if not selected_item_ids:
            messagebox.showinfo("No Selection", "No files selected to delete.")
            return

        try:
            path_column_index = self.tree_columns.index("path")
        except ValueError:
            messagebox.showerror("Configuration Error", "Path column ('path') not found in Treeview setup. Cannot proceed with delete.")
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
                "Path Issues", 
                "Some files could not be processed for deletion due to path issues:\n- " + 
                "\n- ".join(problematic_paths_details) + 
                "\n\nOnly files with valid, recognized paths will be sent for deletion."
            )

        if not files_to_request_delete:
            messagebox.showinfo("No Valid Paths", "No files with paths valid for deletion were selected/processed.")
            return

        confirmed = messagebox.askyesno(
            "Confirm Delete", 
            f"Are you sure you want to request deletion of {len(files_to_request_delete)} file(s) on the server?\n\nFiles to be requested:\n- " +
            "\n- ".join(files_to_request_delete) +
            "\n\nThis action cannot be undone."
        )
        if not confirmed:
            return

        ip = self.ip_entry.get()
        port_str = self.port_entry.get()
        if not ip or not port_str: # Should be validated by perform_search, but good to check
            messagebox.showerror("Connection Error", "Server IP or Port not set.")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Input Error", "Invalid Port number.")
            return

        delete_payload = { "command": "delete", "files": files_to_request_delete }
        
        # Disable buttons during operation
        self.delete_button.config(state=tk.DISABLED)
        self.search_button.config(state=tk.DISABLED) 
        
        response = send_request_to_server(ip, port, delete_payload)
        
        # Re-enable buttons
        self.delete_button.config(state=tk.NORMAL)
        self.search_button.config(state=tk.NORMAL)

        deleted_count = 0
        error_messages_from_server = []

        if response and response.get("status") == "success" and "results" in response:
            for result in response["results"]:
                if result.get("status") == "deleted":
                    deleted_count += 1
                else:
                    error_messages_from_server.append(f"File '{result.get('file', 'Unknown file')}': {result.get('message', 'Unknown error')}")
            
            summary_message = f"Server processed deletion request.\nSuccessfully deleted: {deleted_count} file(s)."
            if error_messages_from_server:
                summary_message += "\n\nErrors reported by server for specific files:\n" + "\n".join(error_messages_from_server)
            messagebox.showinfo("Deletion Report", summary_message)
            
            # Refresh search results to reflect deletions
            print("Refreshing search results after deletion attempt...")
            self.perform_search() # This will re-use the existing search parameters
            
        elif response and "error" in response:
            messagebox.showerror("Deletion Request Error", f"Server returned an error: {response['error']}")
        else:
            messagebox.showerror("Deletion Request Error", "Failed to get a valid response from the server during delete operation. Check connection and server logs.")

    def perform_search(self):
        # Clear previous results
        for i in self.tree.get_children():
            self.tree.delete(i)

        ip = self.ip_entry.get()
        port_str = self.port_entry.get()
        mask = self.mask_entry.get()
        
        # Get values from new filter widgets
        case_sensitive = self.case_sensitive_var.get()
        type_filter = self.type_filter_var.get().lower() # Convert to lowercase for server

        if not ip:
            messagebox.showerror("Error", "Server IP cannot be empty.")
            return
        if not port_str:
            messagebox.showerror("Error", "Server Port cannot be empty.")
            return
        if not mask:
            messagebox.showerror("Error", "File Mask cannot be empty.")
            return
        
        try:
            port = int(port_str)
            if not (0 < port < 65536):
                 raise ValueError("Port number out of range.")
        except ValueError:
            messagebox.showerror("Error", "Invalid Port number. Must be an integer between 1 and 65535.")
            return

        self.search_button.config(state=tk.DISABLED) # Disable button during search
        
        # Call the existing network function, now with more parameters
        response = search_files_on_server(ip, port, mask, case_sensitive, type_filter)
        
        self.search_button.config(state=tk.NORMAL) # Re-enable button

        if response is None: # Should not happen if search_files_on_server always returns a dict
            messagebox.showerror("Error", "Failed to get a response from the server function.")
            return

        if "error" in response:
            messagebox.showerror("Search Error", f"Server or connection error: {response['error']}")
        elif "results" in response and isinstance(response["results"], list):
            file_list = response["results"]
            if not file_list:
                messagebox.showinfo("No Results", "No files found matching your criteria.")
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
