import socket
import os
import datetime
import fnmatch
import json
import logging

# --- Logging Setup ---
logging.basicConfig(filename='server.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- File Type Definitions ---
FILE_TYPE_MAPPING = {
    "documents": {".txt", ".doc", ".docx", ".pdf", ".odt", ".rtf"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"},
    "archives": {".zip", ".rar", ".tar", ".gz", ".7z"},
}

# --- File Searching Functionality ---
def search_files(directory_path, file_mask, case_sensitive=False, type_filter="any"):
    """
    Recursively searches for files matching a given mask and type in a directory.

    Args:
        directory_path (str): The path to the directory to search.
        file_mask (str): The file mask to match (e.g., "*.txt", "report.*").
        case_sensitive (bool): If True, matching is case-sensitive. Default False.
        type_filter (str): Filter by type ("documents", "images", "archives", or "any").
                           Default "any".

    Returns:
        list: A list of dictionaries, where each dictionary contains details
              of a found file (name, path, size, modified_date, extension).
    """
    found_files = []
    if not os.path.isdir(directory_path):
        print(f"Warning: Directory not found or not accessible: {directory_path}")
        return found_files

    # Determine allowed extensions if a type_filter is active
    allowed_extensions = set()
    if type_filter != "any" and type_filter in FILE_TYPE_MAPPING:
        allowed_extensions = FILE_TYPE_MAPPING[type_filter]
    elif type_filter != "any":
        print(f"Warning: Unknown type_filter '{type_filter}'. It will be ignored.")
        # Proceed as if type_filter was "any" if it's an unknown category

    for root, _, files in os.walk(directory_path, topdown=True, onerror=None):
        for filename in files:
            # Case sensitivity for fnmatch
            matches_mask = False
            if case_sensitive:
                if fnmatch.fnmatch(filename, file_mask):
                    matches_mask = True
            else:
                if fnmatch.fnmatch(filename.lower(), file_mask.lower()):
                    matches_mask = True
            
            if matches_mask:
                # Type filtering
                _, extension = os.path.splitext(filename)
                extension_lower = extension.lower()

                if type_filter != "any" and allowed_extensions: # type_filter is valid and has extensions
                    if extension_lower not in allowed_extensions:
                        continue # Skip this file, does not match type filter
                
                full_path = os.path.join(root, filename)
                try:
                    stat_info = os.stat(full_path)
                    size = stat_info.st_size
                    modified_timestamp = stat_info.st_mtime
                    modified_date = datetime.datetime.fromtimestamp(modified_timestamp).isoformat()
                    _, extension = os.path.splitext(filename)

                    found_files.append({
                        "name": filename,
                        "path": full_path,
                        "size": size,
                        "modified_date": modified_date,
                        "extension": extension,
                    })
                except OSError as e:
                    print(f"Warning: Could not access file {full_path}: {e}")
    return found_files

# --- Server Functionality ---
def start_server():
    host = '0.0.0.0'
    port = 54321

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Set SO_REUSEADDR to allow fast restarts of the server
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
    except socket.error as e:
        print(f"Error binding port: {e}")
        return

    server_socket.listen(5)
    print(f"Server listening on {host}:{port}")

    # Define a fixed search path for the server for security and simplicity.
    # In a real application, this would be configurable and secured.
    # For testing, we'll use a temporary directory that we create.
    fixed_search_directory = "/tmp/shared_test_folder_server"


    try:
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"Client connected from {client_address}")
            
            response_data = {}
            try:
                # Receive data from the client
                # Assuming the request is small enough to be received in one go (max 4096 bytes)
                # Note: For robust handling of larger messages, chunked receiving would be needed.
                request_bytes = client_socket.recv(4096)
                if not request_bytes:
                    print(f"Client {client_address} disconnected without sending data.")
                    client_socket.close()
                    continue

                request_str = request_bytes.decode('utf-8')
                request_json = json.loads(request_str)
                print(f"Received from {client_address}: {request_json}")

                client_command = request_json.get("command")
                client_path = request_json.get("path") # Parsed, but server uses fixed_search_directory
                client_mask = request_json.get("mask")
                
                # Get new parameters with defaults
                client_case_sensitive = request_json.get("case_sensitive", False) # Default to False
                client_type_filter = request_json.get("type_filter", "any")     # Default to "any"


                if client_command == "search":
                    if client_mask is not None:
                        logging.info(
                            f"Search request from {client_address}: mask='{client_mask}', "
                            f"case_sensitive={client_case_sensitive}, type_filter='{client_type_filter}'"
                        )
                        # Using fixed_search_directory instead of client_path for security
                        search_results = search_files(
                            fixed_search_directory, 
                            client_mask,
                            case_sensitive=client_case_sensitive,
                            type_filter=client_type_filter
                        )
                        response_data = {"status": "success", "results": search_results}
                    else:
                        logging.warning(f"Search request from {client_address} missing 'mask'.")
                        response_data = {"error": "Missing 'mask' in search command"}
                
                elif client_command == "delete":
                    files_to_delete = request_json.get("files", [])
                    delete_results = []
                    logging.info(f"Delete request from {client_address} for files: {files_to_delete}")

                    if not isinstance(files_to_delete, list):
                        logging.warning(f"Delete request from {client_address} 'files' is not a list.")
                        response_data = {"error": "'files' parameter must be a list."}
                    else:
                        for client_filepath in files_to_delete:
                            if not client_filepath or '..' in client_filepath or os.path.isabs(client_filepath):
                                msg = f"Invalid or potentially unsafe path requested for deletion by {client_address}: '{client_filepath}'"
                                logging.warning(msg)
                                delete_results.append({"file": client_filepath, "status": "error", "message": "Invalid file path."})
                                continue

                            # Construct full path and normalize it
                            # client_filepath is treated as relative to fixed_search_directory
                            full_filepath_to_delete = os.path.join(fixed_search_directory, client_filepath)
                            
                            # Security check: Ensure the path is within the fixed_search_directory
                            # Resolve both paths to their absolute forms to prevent directory traversal
                            abs_fixed_search_dir = os.path.abspath(fixed_search_directory)
                            abs_full_filepath_to_delete = os.path.abspath(full_filepath_to_delete)

                            if os.path.commonprefix([abs_full_filepath_to_delete, abs_fixed_search_dir]) != abs_fixed_search_dir:
                                msg = (f"Security alert: Attempt to delete file '{full_filepath_to_delete}' "
                                       f"outside of designated root '{abs_fixed_search_dir}' by {client_address}.")
                                logging.error(msg)
                                delete_results.append({"file": client_filepath, "status": "error", "message": "Access denied: Cannot delete files outside shared directory."})
                                continue
                            
                            try:
                                if os.path.exists(abs_full_filepath_to_delete) and os.path.isfile(abs_full_filepath_to_delete):
                                    os.remove(abs_full_filepath_to_delete)
                                    msg = f"Successfully deleted file: {abs_full_filepath_to_delete}"
                                    logging.info(msg)
                                    delete_results.append({"file": client_filepath, "status": "deleted"})
                                elif not os.path.exists(abs_full_filepath_to_delete):
                                    msg = f"File not found for deletion: {abs_full_filepath_to_delete}"
                                    logging.warning(msg)
                                    delete_results.append({"file": client_filepath, "status": "error", "message": "File not found."})
                                else: # Path exists but is not a file (e.g. a directory)
                                    msg = f"Path is not a file, cannot delete: {abs_full_filepath_to_delete}"
                                    logging.warning(msg)
                                    delete_results.append({"file": client_filepath, "status": "error", "message": "Path is not a file."})

                            except (OSError, Exception) as e: # Catch broader exceptions for os.remove
                                msg = f"Error deleting file {abs_full_filepath_to_delete}: {e}"
                                logging.error(msg)
                                delete_results.append({"file": client_filepath, "status": "error", "message": str(e)})
                        response_data = {"status": "success", "results": delete_results}
                
                else:
                    logging.warning(f"Unknown command '{client_command}' from {client_address}.")
                    response_data = {"error": "Unknown command"}

            except json.JSONDecodeError:
                logging.error(f"Invalid JSON received from {client_address}: {request_bytes[:200]}") # Log part of the message
                print(f"Invalid JSON received from {client_address}")
                response_data = {"error": "Invalid JSON format"}
            except Exception as e:
                print(f"An error occurred processing request from {client_address}: {e}")
                response_data = {"error": f"Server error: {e}"}
            finally:
                if response_data: # Ensure response_data is not empty
                    try:
                        client_socket.sendall(json.dumps(response_data).encode('utf-8'))
                    except socket.error as send_e:
                        print(f"Error sending response to {client_address}: {send_e}")
                client_socket.close()
                print(f"Connection with {client_address} closed.")
                
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        if server_socket:
            server_socket.close()
            print("Server socket closed.")

if __name__ == '__main__':
    # --- Setup for server's fixed search directory ---
    server_search_dir = "/tmp/shared_test_folder_server" # Same as fixed_search_directory in start_server
    server_sub_dir = os.path.join(server_search_dir, "server_sub")
    
    print(f"Setting up test directory for server at: {server_search_dir}")
    os.makedirs(server_sub_dir, exist_ok=True)
    
    # Create sample files for testing filters
    sample_files_to_create = {
        "server_doc1.txt": "Server test document 1 (to be kept).",
        "SERVER_DOC1_UPPER.TXT": "Server test document 1, uppercase name (to be kept).",
        "server_image.jpg": "Fake image data (to be kept).",
        "Server_Image_Mixed.JpG": "Fake image data, mixed case ext (to be kept).",
        "server_archive.zip": "Fake archive data (to be kept).",
        "another_doc.pdf": "A PDF document (to be kept).",
        "script.py": "A python script, not in defined types (to be kept).",
        "file_to_delete1.txt": "This file is intended for deletion.",
        "file_to_delete2.log": "Another file to be deleted.",
        os.path.join(server_sub_dir, "sub_doc.txt"): "Subdirectory document (to be kept).",
        os.path.join(server_sub_dir, "SUB_IMG.PNG"): "Subdirectory image, uppercase (to be kept).",
        os.path.join(server_sub_dir, "sub_file_to_delete.txt"): "Subdirectory file for deletion.",
    }
    # Ensure all files are created or overwritten for consistent testing
    for file_path_key, content in sample_files_to_create.items():
        # Adjust path joining if the key itself is an absolute path (like those from os.path.join)
        if os.path.isabs(file_path_key):
            full_file_path = file_path_key
        else:
            full_file_path = os.path.join(server_search_dir, file_path_key)
        
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        with open(full_file_path, "w") as f:
            f.write(content)
    print("Test directory and sample files for server created/updated.\n")

    # --- Comment out direct search_files tests if not needed for this specific task ---
    # print("--- Direct search_files tests (before starting server) ---")
    # ... (previous test calls were here) ...
    # print("--- End of direct search_files tests ---\n")
    
    logging.info("Server script started. Test directory and files prepared.")
    print("Server starting. Logging to server.log. Test files for deletion created.")
    start_server()
