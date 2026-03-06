import sys
import time
import logging
import webview
import threading
import dash_bootstrap_components as dbc
from dash import Dash
from abc import ABC, abstractmethod
from PIL import Image
from typing import Optional, Any
from .utils import get_idle_host_port

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DeskDashApp(ABC):
    """
    Abstract base class for building Dash applications that run as desktop applications.
    
    Features:
    - Runs Dash app in a local webview window (like a desktop app)
    
    Subclasses must implement:
    - create_layout(): Return the Dash app layout
    - on_quit(): Optional cleanup function called before shutdown
    """
    
    def __init__(self, app_name: str = "Dash App", window_width: int = 1200, window_height: int = 800, icon_image: Optional[Image.Image] = None, *args, **kwargs):
        """
        Initialize the DeskDashApp.
        
        Args:
            app_name: Name of the application (shown in window title and tray)
            window_width: Initial window width in pixels
            window_height: Initial window height in pixels
            icon_image: Optional PIL Image for the tray icon
            *args, **kwargs: Additional arguments passed to Dash constructor
        
        Defaults to using the LUX Bootstrap theme if no external stylesheets are provided.
        """
        self.app_name = app_name
        self.window_width = window_width
        self.window_height = window_height
        self.icon_image = icon_image
        
        # Dash app instance
        self.dash_app: Optional[Dash] = None
        self.server: Optional[Any] = None
        
        # Webview window
        self.webview_window: Optional[Any] = None
        
        # State flags
        self.is_running = True
        # ensure Darkly theme is applied
        styles = kwargs.pop("external_stylesheets", None)
        if styles is None:
            styles = [dbc.themes.LUX]
        else:
            # append Darkly if other styles were provided
            styles = list(styles) + [dbc.themes.LUX]
        kwargs["external_stylesheets"] = styles
        self.args = args
        self.kwargs = kwargs
        
        # Host and port will be set when run() is called
        self.host: str = '127.0.0.1'
        self.port: int = 8050
        
    @abstractmethod
    def create_layout(self):
        """
        Create and return the Dash app layout.
        Subclasses must implement this method.
        
        Returns:
            Dash layout (html component or list of components)
        """
        raise NotImplementedError("Subclasses must implement create_layout()")
    
    def on_quit(self):
        """
        Optional cleanup function called before shutdown.
        Override this method in subclasses for custom cleanup logic.
        """
        pass
    
    def setup_callbacks(self):
        """
        Setup Dash callbacks for the application.
        Override this method in subclasses to define custom callbacks.
        
        Example:
            @self.dash_app.callback(
                Output('my-div', 'children'),
                Input('my-button', 'n_clicks')
            )
            def update_output(n_clicks):
                return f'Button clicked {n_clicks} times'
        """
        pass
    
    def _setup_dash_app(self, args, kwargs):
        """Initialize and configure the Dash application."""
        self.dash_app = Dash(__name__, *args, **kwargs)
        self.dash_app.layout = self.create_layout()
        self.setup_callbacks()
        self.server = self.dash_app.server
    
    def _on_window_close(self):
        """Handle window close event - quitting."""
        # Prevent re-entry on recursive close events
        if not self.is_running:
            return
        
        # Set flag to stop running BEFORE destroying window
        self.is_running = False
        
        logger.info("Closing application...")
        self.on_quit()
        
        # Close the webview window
        if self.webview_window:
            self.webview_window.destroy()
        
        # Exit all processes
        logger.info("Shutting down all processes...")
        sys.exit(0)
    
    def _run_webview(self, debug: bool = False):
        """Create and run the webview window on the main thread."""
        self.webview_window = webview.create_window(
            title=self.app_name,
            url=f'http://{self.host}:{self.port}',
            width=self.window_width,
            height=self.window_height
        )
        
        # Set close callback
        self.webview_window.events.closing += self._on_window_close
        
        # Start webview on the main thread (required by pywebview)
        webview.start(debug=False)
    
    def run(self, debug: bool = False, port: int = 8050, host: str = '127.0.0.1', auto_detect: bool = True):
        """
        Run the desktop application.
        
        Args:
            debug: Enable Dash debug mode
            port: Preferred port number for the local server (default: 8050)
            host: Preferred host address (default: '127.0.0.1')
            auto_detect: If True, automatically find idle host:port if preferred ones are in use (default: True)
        """
        try:
            # Auto-detect idle host and port if requested
            if auto_detect:
                self.host, self.port = get_idle_host_port(
                    preferred_port=port,
                    preferred_host=host,
                    port_search_range=10
                )
            else:
                self.host = host
                self.port = port
            
            logger.info(f"Starting application on {self.host}:{self.port}")
            
            # Setup Dash app
            self._setup_dash_app(self.args, self.kwargs)
            
            # Run Dash server in a separate thread
            dash_thread = threading.Thread(
                target=lambda: self.dash_app.run(
                    debug=debug,
                    port=self.port,
                    host=self.host,
                    use_reloader=False
                ),
                daemon=True
            )
            dash_thread.start()
            
            # Give server time to start
            time.sleep(1)
            
            # Run webview on the main thread (required by pywebview)
            self._run_webview(debug=debug)
            
        except Exception as e:
            logger.error(f"Error running application: {e}")
            self.on_quit()
            raise

