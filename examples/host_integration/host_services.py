# examples/host_integration/host_services.py
"""
Example host service implementations for AgentMap integration.

This file demonstrates how to implement services that work with host-defined protocols
and integrate seamlessly with AgentMap's dependency injection system.
"""

import logging
import sqlite3
import smtplib
import json
import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class DatabaseService:
    """
    Example database service for host application integration.
    
    This service provides database operations that can be injected into
    agents implementing the DatabaseServiceProtocol.
    """
    
    def __init__(self, database_path: str = "host_app.db", logger: Optional[logging.Logger] = None):
        """
        Initialize database service.
        
        Args:
            database_path: Path to SQLite database file
            logger: Optional logger for database operations
        """
        self.database_path = database_path
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.connection = None
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database with example tables."""
        try:
            self.connection = sqlite3.connect(self.database_path)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
            
            # Create example tables
            cursor = self.connection.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Log entries table for AgentMap integration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    graph_name TEXT,
                    operation TEXT NOT NULL,
                    result TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
            self.logger.info(f"Database initialized at {self.database_path}")
            
            # Insert sample data if tables are empty
            self._insert_sample_data()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _insert_sample_data(self) -> None:
        """Insert sample data for demonstration."""
        try:
            cursor = self.connection.cursor()
            
            # Check if data already exists
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] > 0:
                return  # Data already exists
            
            # Insert sample users
            sample_users = [
                ("Alice Johnson", "alice@example.com"),
                ("Bob Smith", "bob@example.com"),
                ("Carol Brown", "carol@example.com")
            ]
            
            cursor.executemany("INSERT INTO users (name, email) VALUES (?, ?)", sample_users)
            
            # Insert sample tasks
            sample_tasks = [
                (1, "Review documentation", "Review and update AgentMap integration docs", "completed", "high"),
                (1, "Setup database", "Configure database for host application", "completed", "medium"),
                (2, "Test email service", "Verify email notifications are working", "in_progress", "medium"),
                (2, "Deploy to production", "Deploy host application with AgentMap integration", "pending", "high"),
                (3, "Create user guide", "Write user guide for new features", "pending", "low")
            ]
            
            cursor.executemany("""
                INSERT INTO tasks (user_id, title, description, status, priority) 
                VALUES (?, ?, ?, ?, ?)
            """, sample_tasks)
            
            self.connection.commit()
            self.logger.info("Sample data inserted into database")
            
        except Exception as e:
            self.logger.error(f"Failed to insert sample data: {e}")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            List of dictionaries representing query results
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # For SELECT queries, return results
            if query.strip().upper().startswith('SELECT'):
                results = [dict(row) for row in cursor.fetchall()]
                self.logger.debug(f"Query returned {len(results)} rows")
                return results
            else:
                # For INSERT/UPDATE/DELETE, commit and return affected rows
                self.connection.commit()
                affected_rows = cursor.rowcount
                self.logger.debug(f"Query affected {affected_rows} rows")
                return [{"affected_rows": affected_rows}]
                
        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            raise
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users from database."""
        return self.execute_query("SELECT * FROM users ORDER BY name")
    
    def get_tasks_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get tasks for a specific user."""
        return self.execute_query("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at", (user_id,))
    
    def log_agent_operation(self, agent_name: str, operation: str, result: str, graph_name: Optional[str] = None) -> None:
        """Log an agent operation to the database."""
        self.execute_query(
            "INSERT INTO agent_logs (agent_name, graph_name, operation, result) VALUES (?, ?, ?, ?)",
            (agent_name, graph_name, operation, result)
        )
    
    def get_agent_logs(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get agent operation logs."""
        if agent_name:
            return self.execute_query(
                "SELECT * FROM agent_logs WHERE agent_name = ? ORDER BY timestamp DESC",
                (agent_name,)
            )
        else:
            return self.execute_query("SELECT * FROM agent_logs ORDER BY timestamp DESC")
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.logger.info("Database connection closed")


class EmailService:
    """
    Example email service for host application integration.
    
    This service provides email functionality that can be injected into
    agents implementing the EmailServiceProtocol.
    """
    
    def __init__(self, smtp_host: str = "localhost", smtp_port: int = 587, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize email service.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            username: SMTP username (optional)
            password: SMTP password (optional)
            logger: Optional logger for email operations
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # For demo purposes, we'll simulate email sending
        self.demo_mode = True
        self.sent_emails = []  # Store sent emails for demo
    
    def send_email(self, to_email: str, subject: str, body: str, 
                   from_email: Optional[str] = None, html: bool = False) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            from_email: Sender email address (optional)
            html: Whether body contains HTML content
            
        Returns:
            True if email sent successfully
        """
        try:
            email_data = {
                "to": to_email,
                "from": from_email or "noreply@hostapp.example",
                "subject": subject,
                "body": body,
                "html": html,
                "timestamp": datetime.now().isoformat(),
                "status": "sent"
            }
            
            if self.demo_mode:
                # In demo mode, just store the email
                self.sent_emails.append(email_data)
                self.logger.info(f"📧 Demo email sent to {to_email}: {subject}")
                return True
            else:
                # Real email sending (commented out for demo)
                # msg = MIMEMultipart('alternative') if html else MIMEText(body)
                # msg['Subject'] = subject
                # msg['From'] = from_email or "noreply@hostapp.example"
                # msg['To'] = to_email
                # 
                # if html:
                #     msg.attach(MIMEText(body, 'html'))
                # 
                # with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                #     if self.username and self.password:
                #         server.starttls()
                #         server.login(self.username, self.password)
                #     server.send_message(msg)
                
                self.logger.info(f"Email sent to {to_email}: {subject}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_notification_email(self, to_email: str, agent_name: str, 
                              operation: str, result: str) -> bool:
        """
        Send a notification email about an agent operation.
        
        Args:
            to_email: Recipient email address
            agent_name: Name of the agent that performed the operation
            operation: Description of the operation
            result: Result of the operation
            
        Returns:
            True if email sent successfully
        """
        subject = f"AgentMap Notification: {agent_name} - {operation}"
        
        body = f"""
        AgentMap Host Application Notification
        
        Agent: {agent_name}
        Operation: {operation}
        Result: {result}
        Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        This is an automated notification from your AgentMap host application.
        """
        
        return self.send_email(to_email, subject, body.strip())
    
    def get_sent_emails(self) -> List[Dict[str, Any]]:
        """Get list of sent emails (demo mode only)."""
        return self.sent_emails.copy()


class NotificationService:
    """
    Example notification service for multi-channel messaging.
    
    This service provides notification functionality through various channels
    that can be injected into agents implementing the NotificationServiceProtocol.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize notification service.
        
        Args:
            config: Configuration for various notification channels
            logger: Optional logger for notification operations
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.sent_notifications = []  # Store notifications for demo
    
    def send_notification(self, channel: str, message: str, 
                         recipient: Optional[str] = None, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a notification through the specified channel.
        
        Args:
            channel: Notification channel (slack, teams, webhook, etc.)
            message: Notification message
            recipient: Optional recipient identifier
            metadata: Optional additional metadata
            
        Returns:
            True if notification sent successfully
        """
        try:
            notification_data = {
                "channel": channel,
                "message": message,
                "recipient": recipient,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat(),
                "status": "sent"
            }
            
            # For demo purposes, just store the notification
            self.sent_notifications.append(notification_data)
            
            if channel == "slack":
                self._send_slack_notification(message, recipient, metadata)
            elif channel == "teams":
                self._send_teams_notification(message, recipient, metadata)
            elif channel == "webhook":
                self._send_webhook_notification(message, recipient, metadata)
            elif channel == "console":
                self._send_console_notification(message, recipient, metadata)
            else:
                self.logger.warning(f"Unknown notification channel: {channel}")
                return False
            
            self.logger.info(f"📢 Notification sent via {channel}: {message[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification via {channel}: {e}")
            return False
    
    def _send_slack_notification(self, message: str, recipient: Optional[str], 
                                metadata: Optional[Dict[str, Any]]) -> None:
        """Send Slack notification (demo implementation)."""
        # In a real implementation, this would use Slack API
        self.logger.info(f"🔔 [SLACK] To {recipient or '#general'}: {message}")
    
    def _send_teams_notification(self, message: str, recipient: Optional[str], 
                                metadata: Optional[Dict[str, Any]]) -> None:
        """Send Teams notification (demo implementation)."""
        # In a real implementation, this would use Teams API
        self.logger.info(f"🔔 [TEAMS] To {recipient or 'General'}: {message}")
    
    def _send_webhook_notification(self, message: str, recipient: Optional[str], 
                                  metadata: Optional[Dict[str, Any]]) -> None:
        """Send webhook notification (demo implementation)."""
        # In a real implementation, this would POST to a webhook URL
        webhook_url = self.config.get("webhook_url", "https://example.com/webhook")
        self.logger.info(f"🔔 [WEBHOOK] To {webhook_url}: {message}")
    
    def _send_console_notification(self, message: str, recipient: Optional[str], 
                                  metadata: Optional[Dict[str, Any]]) -> None:
        """Send console notification (demo implementation)."""
        print(f"🔔 [NOTIFICATION] {message}")
    
    def send_agent_notification(self, agent_name: str, operation: str, 
                              result: str, channels: List[str] = None) -> Dict[str, bool]:
        """
        Send notifications about an agent operation to multiple channels.
        
        Args:
            agent_name: Name of the agent
            operation: Operation that was performed
            result: Result of the operation
            channels: List of channels to notify (defaults to all configured)
            
        Returns:
            Dictionary mapping channel names to success status
        """
        if channels is None:
            channels = ["console", "slack"]  # Default channels
        
        message = f"Agent '{agent_name}' completed operation '{operation}' with result: {result}"
        
        results = {}
        for channel in channels:
            results[channel] = self.send_notification(channel, message)
        
        return results
    
    def get_sent_notifications(self) -> List[Dict[str, Any]]:
        """Get list of sent notifications (demo mode)."""
        return self.sent_notifications.copy()


class FileService:
    """
    Example file service for document and file operations.
    
    This service provides file management functionality that can be injected into
    agents implementing the FileServiceProtocol.
    """
    
    def __init__(self, storage_path: str = "host_app_files", 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize file service.
        
        Args:
            storage_path: Base path for file storage
            logger: Optional logger for file operations
        """
        self.storage_path = Path(storage_path)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(exist_ok=True)
        self.logger.info(f"File service initialized with storage path: {self.storage_path}")
    
    def save_file(self, filename: str, content: Union[str, bytes], 
                  subfolder: Optional[str] = None) -> str:
        """
        Save content to a file.
        
        Args:
            filename: Name of the file
            content: File content (string or bytes)
            subfolder: Optional subfolder within storage path
            
        Returns:
            Full path to the saved file
        """
        try:
            # Determine target directory
            if subfolder:
                target_dir = self.storage_path / subfolder
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_dir = self.storage_path
            
            file_path = target_dir / filename
            
            # Write content based on type
            if isinstance(content, str):
                file_path.write_text(content, encoding='utf-8')
            else:
                file_path.write_bytes(content)
            
            self.logger.info(f"File saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to save file {filename}: {e}")
            raise
    
    def read_file(self, filename: str, subfolder: Optional[str] = None) -> str:
        """
        Read content from a file.
        
        Args:
            filename: Name of the file
            subfolder: Optional subfolder within storage path
            
        Returns:
            File content as string
        """
        try:
            if subfolder:
                file_path = self.storage_path / subfolder / filename
            else:
                file_path = self.storage_path / filename
            
            content = file_path.read_text(encoding='utf-8')
            self.logger.info(f"File read: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to read file {filename}: {e}")
            raise
    
    def list_files(self, subfolder: Optional[str] = None) -> List[str]:
        """
        List files in the storage directory or subfolder.
        
        Args:
            subfolder: Optional subfolder to list
            
        Returns:
            List of filenames
        """
        try:
            if subfolder:
                target_dir = self.storage_path / subfolder
            else:
                target_dir = self.storage_path
            
            if not target_dir.exists():
                return []
            
            files = [f.name for f in target_dir.iterdir() if f.is_file()]
            self.logger.debug(f"Listed {len(files)} files in {target_dir}")
            return sorted(files)
            
        except Exception as e:
            self.logger.error(f"Failed to list files in {subfolder or 'root'}: {e}")
            return []
    
    def save_agent_output(self, agent_name: str, output_data: Any, 
                         graph_name: Optional[str] = None) -> str:
        """
        Save agent output to a file.
        
        Args:
            agent_name: Name of the agent
            output_data: Data to save
            graph_name: Optional graph name for organization
            
        Returns:
            Path to saved file
        """
        # Create subfolder for agent outputs
        subfolder = "agent_outputs"
        if graph_name:
            subfolder = f"agent_outputs/{graph_name}"
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_name}_{timestamp}.json"
        
        # Convert output data to JSON
        content = json.dumps(output_data, indent=2, default=str)
        
        return self.save_file(filename, content, subfolder)


# Factory functions for creating services with proper configuration
def create_database_service(app_config_service, logging_service) -> DatabaseService:
    """
    Factory function for creating database service.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
        
    Returns:
        Configured DatabaseService instance
    """
    # Get configuration from app config service
    config = app_config_service.get_host_service_config("database_service").get("configuration", {})
    logger = logging_service.get_logger("host.database_service")
    
    database_path = config.get("database_path", "host_app.db")
    return DatabaseService(database_path, logger)


def create_email_service(app_config_service, logging_service) -> EmailService:
    """
    Factory function for creating email service.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
        
    Returns:
        Configured EmailService instance
    """
    # Get configuration from app config service
    config = app_config_service.get_host_service_config("email_service").get("configuration", {})
    logger = logging_service.get_logger("host.email_service")
    
    # Set demo mode from config
    email_service = EmailService(
        smtp_host=config.get("smtp_host", "localhost"),
        smtp_port=config.get("smtp_port", 587),
        username=config.get("username"),
        password=config.get("password"),
        logger=logger
    )
    
    # Apply demo mode setting
    email_service.demo_mode = config.get("demo_mode", True)
    
    return email_service


def create_notification_service(app_config_service, logging_service) -> NotificationService:
    """
    Factory function for creating notification service.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
        
    Returns:
        Configured NotificationService instance
    """
    # Get configuration from app config service
    config = app_config_service.get_host_service_config("notification_service").get("configuration", {})
    logger = logging_service.get_logger("host.notification_service")
    
    return NotificationService(config, logger)


def create_file_service(app_config_service, logging_service) -> FileService:
    """
    Factory function for creating file service.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
        
    Returns:
        Configured FileService instance
    """
    # Get configuration from app config service
    config = app_config_service.get_host_service_config("file_service").get("configuration", {})
    logger = logging_service.get_logger("host.file_service")
    
    storage_path = config.get("storage_path", "host_app_files")
    return FileService(storage_path, logger)
