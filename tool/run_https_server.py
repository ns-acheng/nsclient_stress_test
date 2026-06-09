import argparse
import logging
import os
import sys
import ssl
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Import pyopenssl for cert generation
try:
    from OpenSSL import crypto
except ImportError:
    print("Error: pyopenssl is required. Please run: pip install pyopenssl")
    sys.exit(1)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from util_input import start_input_monitor
except ImportError:
    # Fallback if running standalone without util_input available
    def start_input_monitor(stop_event):
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s" %
                    (self.client_address[0],
                     self.log_date_time_string(),
                     format % args))
    
    def handle(self):
        """Override handle to suppress ConnectionResetError during stress testing."""
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # Expected during high-concurrency stress testing - client closed connection
            pass

def generate_self_signed_cert(cert_path, key_path):
    """Generates a self-signed certificate and key using pyopenssl."""
    logger.info(f"Generating self-signed certificate at {cert_path} and {key_path}")
    
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)
    
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "TestState"
    cert.get_subject().L = "TestCity"
    cert.get_subject().O = "TestOrg"
    cert.get_subject().OU = "TestUnit"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60) # 10 years
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')
    
    with open(cert_path, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_path, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

def main():
    parser = argparse.ArgumentParser(description="Simple HTTPS Server")
    parser.add_argument("--port", type=int, default=443, help="Port to listen on (default: 443)")
    parser.add_argument("--directory", type=str, default=".", help="Directory to serve (default: .)")
    parser.add_argument("--cert", type=str, default="cert.pem", help="Path to certificate file")
    parser.add_argument("--key", type=str, default="key.pem", help="Path to private key file")
    args = parser.parse_args()

    # Resolve paths before changing directory
    target_dir = os.path.abspath(args.directory)
    cert_path = os.path.abspath(args.cert)
    key_path = os.path.abspath(args.key)

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Generate certs if they don't exist
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        try:
            generate_self_signed_cert(cert_path, key_path)
        except Exception as e:
            logger.error(f"Failed to generate certificate: {e}")
            return

    # Change to target directory to serve files correctly
    os.chdir(target_dir)

    handler_class = QuietHandler

    try:
        server = ThreadingHTTPServer(('0.0.0.0', args.port), handler_class)
        
        # Setup SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)

    except PermissionError:
        logger.error(f"Permission denied binding to port {args.port}. Try running as Admin or use a port > 1024.")
        return
    except OSError as e:
        logger.error(f"Failed to start server: {e}")
        return

    logger.info(f"HTTPS Server running on port {args.port}")
    logger.info(f"Serving directory: {target_dir}")
    logger.info(f"Using cert: {cert_path}")
    logger.info(f"Using key: {key_path}")
    logger.info("Press ESC to stop the server")

    stop_event = threading.Event()
    start_input_monitor(stop_event)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping HTTPS server...")
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    main()
