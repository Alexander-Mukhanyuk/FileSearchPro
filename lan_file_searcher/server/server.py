import socket
import os
import datetime
import fnmatch
import json
import logging
import shutil # For copy operation
import threading
import time # For time.sleep in error loops
# socket is already imported by the original script

# --- Discovery Constants ---
DISCOVERY_PORT = 54320
DISCOVERY_REQUEST_MSG = "DISCOVER_FILESEARCH_SERVER_REQUEST_V1"
SERVICE_PORT = 54321 # Main TCP service port
SERVER_NAME = "FileSearch Pro Server" 
PROTOCOL_VERSION = "1.0"

# --- Localization ---
LOC_STRINGS_RU_SERVER = {
    "starting_server": "Запуск сервера на {host}:{port}...",
    "server_shutdown": "Сервер остановлен.",
    "client_connected": "Клиент подключен: {address}",
    "client_disconnected_no_data": "Клиент {address} отключился без отправки данных.",
    "client_disconnected": "Соединение с {address} закрыто.",
    "received_request_summary": "Получен запрос '{command}' от {address}.", # Summary
    "sending_response_summary": "Отправка ответа '{status}' для {address}.", # Summary
    "invalid_json_request": "Неверный JSON запрос от {address}: {data_snippet}",
    "unknown_command": "Неизвестная команда '{command}' от {address}.",
    "search_request": "Запрос поиска от {address}: маска='{mask}', регистр={case_sensitive}, тип='{type_filter}'",
    "missing_mask_search_log": "Запрос поиска от {address} не содержит 'mask'.",
    "error_accessing_path_log": "Ошибка доступа к пути: {path} - {error}", # Log only
    "delete_request": "Запрос на удаление от {address} для файлов: {files_list_count} шт.", # files_list_count instead of full list
    "delete_files_not_list_log": "Запрос на удаление от {address}: 'files' не является списком.",
    "delete_invalid_path_log": "Неверный или потенциально небезопасный путь для удаления от {address}: '{filepath}'",
    "delete_security_alert_path_outside_root_log": "ТРЕВОГА БЕЗОПАСНОСТИ: Попытка удалить файл '{filepath}' вне корневого каталога '{root_dir}' от {address}.",
    "file_deleted_successfully_log": "Файл успешно удален: {filepath}",
    "error_deleting_file_log": "Ошибка удаления файла {filepath}: {error}",
    "file_not_found_for_delete_log": "Файл не найден для удаления: {filepath}",
    "path_not_file_for_delete_log": "Путь не является файлом, не удален: {filepath}",
    # Client-facing error messages (can also be logged)
    "response_missing_mask": "Отсутствует 'mask' в команде поиска.",
    "response_unknown_command": "Неизвестная команда: {command}.",
    "response_invalid_json": "Неверный формат JSON.",
    "response_server_error": "Внутренняя ошибка сервера: {error_details}", # error_details for specific error
    "response_delete_files_not_list": "'files' должен быть списком.",
    "response_delete_invalid_path": "Неверный путь к файлу: {filepath}",
    "response_delete_access_denied": "Доступ запрещен: {filepath}",
    "response_delete_file_not_found": "Файл не найден: {filepath}",
    "response_delete_path_not_file": "Путь не является файлом: {filepath}",
    "response_error_deleting_general": "Ошибка при удалении файла {filepath}.",
    # Copy operation strings
    "copy_request": "Запрос на копирование от {address}: '{source_path}' -> '{dest_folder}'",
    "copy_source_not_found": "Ошибка копирования: исходный файл не найден: {source_path}",
    "copy_dest_not_a_folder": "Ошибка копирования: указанный путь назначения не является папкой или не существует: {dest_folder}",
    "copy_permission_read_source_denied": "Ошибка копирования: нет прав на чтение исходного файла: {source_path}",
    "copy_permission_write_dest_denied": "Ошибка копирования: нет прав на запись в папку назначения: {dest_folder}", # Changed dest_path to dest_folder for consistency
    "file_copied_successfully": "Файл {source_filename} успешно скопирован в {dest_folder}",
    "copy_error_general": "Ошибка копирования файла {source_filename}: {error}",
    "copy_path_validation_failed_log": "Ошибка проверки пути для копирования (файл или назначение не в корневой папке): source '{source_path}', dest_folder '{dest_folder}' от {address}",
    "response_copy_path_validation_failed": "Ошибка проверки пути для копирования (файл или назначение должны быть в общей папке).",
    "response_copy_source_not_found": "Ошибка копирования: исходный файл '{source_path}' не найден.",
    "response_copy_dest_not_a_folder": "Ошибка копирования: путь назначения '{dest_folder}' не является папкой или не существует.",
    "response_copy_permission_read_source": "Ошибка копирования: нет прав на чтение исходного файла '{source_path}'.",
    "response_copy_permission_write_dest": "Ошибка копирования: нет прав на запись в папку назначения '{dest_folder}'.",
    "response_copy_error_general": "Ошибка копирования файла '{source_filename}': {error_details}.",
    # Discovery listener strings
    "discovery_listener_starting": "Запуск UDP-слушателя обнаружения на порту {port}...",
    "discovery_listener_error": "Ошибка UDP-слушателя обнаружения: {error}",
    "discovery_request_received": "Получен запрос на обнаружение от {address}",
    "discovery_response_sent": "Отправлен ответ на обнаружение для {address}",
}

def tr_srv(key, lang='ru', **kwargs):
    if lang == 'ru':
        return LOC_STRINGS_RU_SERVER.get(key, f"MISSING_SRV_STRING: {key}").format(**kwargs)
    return f"UNSUPPORTED_LANG_SRV: {key}" # Fallback

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
        logging.warning(tr_srv("error_accessing_path_log", path=directory_path, error="Directory not found or not accessible"))
        # print(f"Warning: Directory not found or not accessible: {directory_path}") # Replaced by logging
        return found_files

    allowed_extensions = set()
    if type_filter != "any" and type_filter in FILE_TYPE_MAPPING:
        allowed_extensions = FILE_TYPE_MAPPING[type_filter]
    elif type_filter != "any":
        logging.warning(f"Unknown type_filter '{type_filter}' received (will be ignored).") # Internal warning, not localized via tr_srv
        # print(f"Warning: Unknown type_filter '{type_filter}'. It will be ignored.") # Replaced by logging

    for root, _, files in os.walk(directory_path, topdown=True, onerror=None): # onerror could be a lambda calling tr_srv
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
                    logging.warning(tr_srv("error_accessing_path_log", path=full_path, error=str(e)))
                    # print(f"Warning: Could not access file {full_path}: {e}") # Replaced by logging
    return found_files

# --- Server Functionality ---

def udp_discovery_listener():
    discover_socket = None # Ensure it's defined for the finally block
    try:
        discover_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discover_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_BROADCAST is not strictly needed for listening, but good if this socket might also send.
        # discover_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) 
        discover_socket.bind(('', DISCOVERY_PORT)) # Listen on all interfaces

        logging.info(tr_srv("discovery_listener_starting", port=DISCOVERY_PORT))
        print(f"UDP Discovery Listener started on port {DISCOVERY_PORT}") # For console feedback

        while True: 
            try:
                message, client_address = discover_socket.recvfrom(1024) 
                message_str = message.decode('utf-8', errors='ignore')
                # Use logging.debug for potentially noisy messages
                logging.debug(f"UDP Discovery: Received '{message_str}' from {client_address}")

                if message_str == DISCOVERY_REQUEST_MSG:
                    logging.info(tr_srv("discovery_request_received", address=client_address))
                    response_data = {
                        "server_name": SERVER_NAME,
                        "service_port": SERVICE_PORT, # The TCP port
                        "protocol_version": PROTOCOL_VERSION
                    }
                    response_json = json.dumps(response_data)
                    discover_socket.sendto(response_json.encode('utf-8'), client_address)
                    logging.info(tr_srv("discovery_response_sent", address=client_address))
            except Exception as e:
                logging.error(tr_srv("discovery_listener_error", error=str(e)))
                time.sleep(0.1) # Avoid tight loop on repeated errors
    except Exception as e:
        logging.error(tr_srv("discovery_listener_error", error=str(e)))
        print(f"Failed to start UDP Discovery Listener: {e}") # For console feedback
    finally:
        if discover_socket:
            discover_socket.close()
            logging.info("UDP Discovery Listener socket closed.")


def handle_copy_command(payload, client_address, fixed_search_directory):
    source_path_relative = payload.get("source_path")
    dest_folder_relative = payload.get("destination_folder")

    if not source_path_relative or not dest_folder_relative:
        return {"status": "error", "message": "Source path or destination folder not specified."} # TODO: Localize if needed

    logging.info(tr_srv("copy_request", address=client_address, source_path=source_path_relative, dest_folder=dest_folder_relative))

    # Path Construction and Validation
    # Prevent path traversal by ensuring client paths are treated as relative
    if '..' in source_path_relative or os.path.isabs(source_path_relative) or \
       '..' in dest_folder_relative or os.path.isabs(dest_folder_relative):
        logging.warning(tr_srv("copy_path_validation_failed_log", source_path=source_path_relative, dest_folder=dest_folder_relative, address=client_address))
        return {"status": "error", "message": tr_srv("response_copy_path_validation_failed")}

    source_full_path = os.path.abspath(os.path.join(fixed_search_directory, source_path_relative))
    dest_folder_full_path = os.path.abspath(os.path.join(fixed_search_directory, dest_folder_relative))
    
    abs_fixed_search_dir = os.path.abspath(fixed_search_directory)

    if not source_full_path.startswith(abs_fixed_search_dir + os.sep) or \
       not dest_folder_full_path.startswith(abs_fixed_search_dir + os.sep): # Ensure dest is also within root
        # Check if dest_folder_full_path is exactly abs_fixed_search_dir for copying to root itself
        if not (dest_folder_full_path == abs_fixed_search_dir and source_full_path.startswith(abs_fixed_search_dir + os.sep)):
             logging.warning(tr_srv("copy_path_validation_failed_log", source_path=source_path_relative, dest_folder=dest_folder_relative, address=client_address))
             return {"status": "error", "message": tr_srv("response_copy_path_validation_failed")}


    if not os.path.isfile(source_full_path):
        logging.warning(tr_srv("copy_source_not_found", source_path=source_full_path))
        return {"status": "error", "message": tr_srv("response_copy_source_not_found", source_path=source_path_relative)}

    if not os.path.isdir(dest_folder_full_path):
        logging.warning(tr_srv("copy_dest_not_a_folder", dest_folder=dest_folder_full_path))
        return {"status": "error", "message": tr_srv("response_copy_dest_not_a_folder", dest_folder=dest_folder_relative)}

    # Permission Checks
    if not os.access(source_full_path, os.R_OK):
        logging.warning(tr_srv("copy_permission_read_source_denied", source_path=source_full_path))
        return {"status": "error", "message": tr_srv("response_copy_permission_read_source", source_path=source_path_relative)}

    if not os.access(dest_folder_full_path, os.W_OK):
        logging.warning(tr_srv("copy_permission_write_dest_denied", dest_folder=dest_folder_full_path)) # Changed key from dest_path
        return {"status": "error", "message": tr_srv("response_copy_permission_write_dest", dest_folder=dest_folder_relative)} # Changed key

    # Perform Copy Operation
    source_filename = os.path.basename(source_full_path)
    destination_final_path = os.path.join(dest_folder_full_path, source_filename)

    try:
        shutil.copy2(source_full_path, destination_final_path)
        logging.info(tr_srv("file_copied_successfully", source_filename=source_filename, dest_folder=dest_folder_relative))
        return {"status": "success", "message": tr_srv("file_copied_successfully", source_filename=source_filename, dest_folder=dest_folder_relative)}
    except Exception as e: # Catch specific exceptions like IOError, OSError if more granularity is needed
        logging.error(tr_srv("copy_error_general", source_filename=source_filename, error=str(e)))
        return {"status": "error", "message": tr_srv("response_copy_error_general", source_filename=source_filename, error_details=str(e))}


def start_server():
    host = '0.0.0.0'
    port = 54321

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
    except socket.error as e:
        # System-level errors like port binding might not need full localization in logs,
        # but user-facing print messages should be.
        logging.error(f"Error binding port: {e}") # Raw error for dev log
        print(f"Error binding port: {e}") # Keep for console
        return

    server_socket.listen(5)
    logging.info(tr_srv("starting_server", host=host, port=port))
    print(tr_srv("starting_server", host=host, port=port)) # Keep for console

    # Define a fixed search path for the server
    # For testing, we'll use a temporary directory that we create.
    fixed_search_directory = "/tmp/shared_test_folder_server"


    try:
        while True:
            client_socket, client_address = server_socket.accept()
            logging.info(tr_srv("client_connected", address=client_address))
            # print(tr_srv("client_connected", address=client_address)) # Reduce console noise
            
            response_data = {}
            request_json_summary = "N/A" # For logging in case of early errors
            try:
                request_bytes = client_socket.recv(4096)
                if not request_bytes:
                    logging.info(tr_srv("client_disconnected_no_data", address=client_address))
                    client_socket.close()
                    continue

                request_str = request_bytes.decode('utf-8')
                request_json = json.loads(request_str)
                
                client_command = request_json.get("command", "unknown")
                request_json_summary = {k: request_json[k] for k in ('command', 'mask', 'files', 'source_path', 'destination_folder') if k in request_json}
                logging.info(tr_srv("received_request_summary", command=client_command, address=client_address))


                if client_command == "search":
                    client_mask = request_json.get("mask")
                    client_case_sensitive = request_json.get("case_sensitive", False)
                    client_type_filter = request_json.get("type_filter", "any")
                    if client_mask is not None:
                        logging.info(tr_srv("search_request", address=client_address, mask=client_mask, 
                                            case_sensitive=client_case_sensitive, type_filter=client_type_filter))
                        search_results = search_files(
                            fixed_search_directory, 
                            client_mask,
                            case_sensitive=client_case_sensitive,
                            type_filter=client_type_filter
                        )
                        response_data = {"status": "success", "results": search_results}
                    else:
                        logging.warning(tr_srv("missing_mask_search_log", address=client_address))
                        response_data = {"error": tr_srv("response_missing_mask")}
                
                elif client_command == "delete":
                    files_to_delete = request_json.get("files", [])
                    delete_results = []
                    logging.info(tr_srv("delete_request", address=client_address, files_list_count=len(files_to_delete)))

                    if not isinstance(files_to_delete, list):
                        logging.warning(tr_srv("delete_files_not_list_log", address=client_address))
                        response_data = {"error": tr_srv("response_delete_files_not_list")}
                    else:
                        for client_filepath in files_to_delete:
                            if not client_filepath or '..' in client_filepath or os.path.isabs(client_filepath):
                                logging.warning(tr_srv("delete_invalid_path_log", address=client_address, filepath=client_filepath))
                                delete_results.append({"file": client_filepath, "status": "error", "message": tr_srv("response_delete_invalid_path", filepath=client_filepath)})
                                continue
                            
                            full_filepath_to_delete = os.path.join(fixed_search_directory, client_filepath)
                            abs_fixed_search_dir = os.path.abspath(fixed_search_directory)
                            abs_full_filepath_to_delete = os.path.abspath(full_filepath_to_delete)

                            if os.path.commonprefix([abs_full_filepath_to_delete, abs_fixed_search_dir]) != abs_fixed_search_dir:
                                logging.error(tr_srv("delete_security_alert_path_outside_root_log", 
                                                     filepath=full_filepath_to_delete, 
                                                     root_dir=abs_fixed_search_dir, 
                                                     address=client_address))
                                delete_results.append({"file": client_filepath, "status": "error", "message": tr_srv("response_delete_access_denied", filepath=client_filepath)})
                                continue
                            
                            try:
                                if os.path.exists(abs_full_filepath_to_delete) and os.path.isfile(abs_full_filepath_to_delete):
                                    os.remove(abs_full_filepath_to_delete)
                                    logging.info(tr_srv("file_deleted_successfully_log", filepath=abs_full_filepath_to_delete)) # This is for general file deletion
                                    delete_results.append({"file": client_filepath, "status": "deleted"})
                                elif not os.path.exists(abs_full_filepath_to_delete):
                                    logging.warning(tr_srv("file_not_found_for_delete_log", filepath=abs_full_filepath_to_delete))
                                    delete_results.append({"file": client_filepath, "status": "error", "message": tr_srv("response_delete_file_not_found", filepath=client_filepath)})
                                else: 
                                    logging.warning(tr_srv("path_not_file_for_delete_log", filepath=abs_full_filepath_to_delete))
                                    delete_results.append({"file": client_filepath, "status": "error", "message": tr_srv("response_delete_path_not_file", filepath=client_filepath)})
                            except (OSError, Exception) as e:
                                logging.error(tr_srv("error_deleting_file_log", filepath=abs_full_filepath_to_delete, error=str(e))) # General deletion error
                                delete_results.append({"file": client_filepath, "status": "error", "message": tr_srv("response_error_deleting_general", filepath=client_filepath)})
                        response_data = {"status": "success", "results": delete_results}
                
                elif client_command == "copy":
                    response_data = handle_copy_command(request_json, client_address, fixed_search_directory)

                else:
                    logging.warning(tr_srv("unknown_command", command=client_command, address=client_address))
                    response_data = {"error": tr_srv("response_unknown_command", command=client_command)}

            except json.JSONDecodeError:
                logging.error(tr_srv("invalid_json_request", address=client_address, data_snippet=request_bytes[:100])) 
                response_data = {"error": tr_srv("response_invalid_json")}
            except Exception as e:
                # Log the actual exception and stack trace for debugging server-side.
                logging.error(f"Unhandled server error processing request from {client_address} (command: {request_json_summary}): {e}", exc_info=True)
                response_data = {"error": tr_srv("response_server_error", error_details="Internal processing error")} # Generic message to client
            finally:
                if response_data:
                    status_for_log = response_data.get("status", "error" if "error" in response_data else "unknown_status")
                    logging.info(tr_srv("sending_response_summary", status=status_for_log, address=client_address))
                    try:
                        client_socket.sendall(json.dumps(response_data).encode('utf-8'))
                    except socket.error as send_e:
                        logging.error(f"Error sending response to {client_address}: {send_e}")
                client_socket.close()
                logging.info(tr_srv("client_disconnected", address=client_address))
                
    except KeyboardInterrupt:
        logging.info(tr_srv("server_shutdown"))
        print(f"\n{tr_srv('server_shutdown')}") # Keep for console
    finally:
        if server_socket:
            server_socket.close()

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
        "file_to_delete1.txt": "This file is intended for deletion.", # Will be deleted by client test if run
        "file_to_delete2.log": "Another file to be deleted.", # Will be deleted by client test if run
        "file_to_copy.txt": "This file is intended for copying.", # Source for copy test
        os.path.join(server_sub_dir, "sub_doc.txt"): "Subdirectory document (to be kept).",
        os.path.join(server_sub_dir, "SUB_IMG.PNG"): "Subdirectory image, uppercase (to be kept).",
        os.path.join(server_sub_dir, "sub_file_to_delete.txt"): "Subdirectory file for deletion.", # Will be deleted by client test if run
    }
    # Ensure destination for copy exists
    copy_dest_sub_dir = os.path.join(server_search_dir, "copy_dest_folder")
    os.makedirs(copy_dest_sub_dir, exist_ok=True)
    
    # Create/overwrite files
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
    
    # Start the UDP discovery listener thread
    discovery_thread = threading.Thread(target=udp_discovery_listener, daemon=True)
    discovery_thread.setName("DiscoveryThread")
    discovery_thread.start()
    
    print("Server starting. Logging to server.log. Test files for deletion and copy created.")
    print("UDP Discovery Thread started.") # Console feedback
    start_server() # This will block for the TCP server
