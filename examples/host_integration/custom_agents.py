# examples/host_integration/custom_agents.py
"""
Example custom agents that demonstrate host service integration.

These agents show how to implement host service protocols and use
the injected services in agent operations. They follow AgentMap's
agent patterns while extending functionality with host services.
"""

from typing import Dict, Any, Optional
from agentmap.agents.base_agent import BaseAgent

# Import our host protocols
try:
    # Try relative import first (for when used as a package)
    from .host_protocols import (
        DatabaseServiceProtocol,
        EmailServiceProtocol,
        NotificationServiceProtocol,
        FileServiceProtocol,
        FullServiceAgentProtocol
    )
except ImportError:
    # Fall back to absolute import (for direct execution)
    from host_protocols import (
        DatabaseServiceProtocol,
        EmailServiceProtocol,
        NotificationServiceProtocol,
        FileServiceProtocol,
        FullServiceAgentProtocol
    )


class DatabaseAgent(BaseAgent, DatabaseServiceProtocol):
    """
    Example agent that demonstrates database service integration.

    This agent can perform database operations using the injected database service.
    It shows how to implement the DatabaseServiceProtocol and use the service
    in agent operations.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize database agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.database_service = None
        self.logger.debug(f"DatabaseAgent '{name}' initialized")

    def configure_database_service(self, database_service: Any) -> None:
        """
        Configure the agent with a database service.

        Args:
            database_service: Database service instance
        """
        try:
            if not database_service:
                raise ValueError("Database service cannot be None")

            # Validate service has required methods
            required_methods = ['execute_query', 'get_users', 'log_agent_operation']
            for method in required_methods:
                if not hasattr(database_service, method):
                    raise ValueError(f"Database service missing required method: {method}")

            self.database_service = database_service
            self.logger.debug(f"Database service configured for {self.name}")

        except Exception as e:
            self.logger.error(f"Failed to configure database service for {self.name}: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute database operations based on the context and inputs.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            Database operation result dict
        """
        if not self.database_service:
            raise ValueError("Database service not configured")

        operation = self.context.get("operation", "get_users")
        self.database_service.log_agent_operation(
            agent_name=self.name,
            operation=operation,
            result="started",
        )

        if operation == "get_users":
            users = self.database_service.get_users()
            result = {"users": users, "count": len(users)}

        elif operation == "get_tasks":
            user_id = inputs.get("user_id")
            if user_id:
                tasks = self.database_service.get_tasks_for_user(user_id)
                result = {"tasks": tasks, "count": len(tasks), "user_id": user_id}
            else:
                all_tasks = self.database_service.execute_query("SELECT * FROM tasks ORDER BY created_at")
                result = {"tasks": all_tasks, "count": len(all_tasks)}

        elif operation == "custom_query":
            query = inputs.get("query")
            params = inputs.get("params")
            if not query:
                raise ValueError("Custom query operation requires 'query' parameter")
            results = self.database_service.execute_query(query, params)
            result = {"query_results": results, "count": len(results)}

        elif operation == "get_logs":
            logs = self.database_service.get_agent_logs(self.name)
            result = {"logs": logs, "count": len(logs)}

        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.database_service.log_agent_operation(
            agent_name=self.name,
            operation=operation,
            result="completed",
        )

        self.logger.info(f"DatabaseAgent '{self.name}' completed {operation}")
        return result


class EmailAgent(BaseAgent, EmailServiceProtocol):
    """
    Example agent that demonstrates email service integration.

    This agent can send emails and notifications using the injected email service.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize email agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.email_service = None
        self.logger.debug(f"EmailAgent '{name}' initialized")

    def configure_email_service(self, email_service: Any) -> None:
        """
        Configure the agent with an email service.

        Args:
            email_service: Email service instance
        """
        try:
            if not email_service:
                raise ValueError("Email service cannot be None")

            required_methods = ['send_email', 'send_notification_email']
            for method in required_methods:
                if not hasattr(email_service, method):
                    raise ValueError(f"Email service missing required method: {method}")

            self.email_service = email_service
            self.logger.debug(f"Email service configured for {self.name}")

        except Exception as e:
            self.logger.error(f"Failed to configure email service for {self.name}: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute email operations based on the context and inputs.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            Email operation result dict
        """
        if not self.email_service:
            raise ValueError("Email service not configured")

        operation = self.context.get("operation", "send_email")

        if operation == "send_email":
            to_email = inputs.get("to_email")
            subject = inputs.get("subject", "Message from AgentMap")
            body = inputs.get("body", "This is a message from an AgentMap agent.")

            if not to_email:
                raise ValueError("'to_email' parameter is required for send_email operation")

            success = self.email_service.send_email(to_email, subject, body)
            result = {"email_sent": success, "to": to_email, "subject": subject}

        elif operation == "send_notification":
            to_email = inputs.get("to_email")
            operation_name = self.context.get("operation_name", "Agent Operation")
            operation_result = self.context.get("operation_result", "Completed")

            if not to_email:
                raise ValueError("'to_email' parameter is required for send_notification operation")

            success = self.email_service.send_notification_email(
                to_email, self.name, operation_name, operation_result
            )
            result = {"notification_sent": success, "to": to_email}

        elif operation == "get_sent_emails":
            sent_emails = self.email_service.get_sent_emails()
            result = {"sent_emails": sent_emails, "count": len(sent_emails)}

        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.logger.info(f"EmailAgent '{self.name}' completed {operation}")
        return result


class NotificationAgent(BaseAgent, NotificationServiceProtocol):
    """
    Example agent that demonstrates notification service integration.

    This agent can send notifications through various channels using
    the injected notification service.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize notification agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.notification_service = None
        self.logger.debug(f"NotificationAgent '{name}' initialized")

    def configure_notification_service(self, notification_service: Any) -> None:
        """
        Configure the agent with a notification service.

        Args:
            notification_service: Notification service instance
        """
        try:
            if not notification_service:
                raise ValueError("Notification service cannot be None")

            required_methods = ['send_notification', 'send_agent_notification']
            for method in required_methods:
                if not hasattr(notification_service, method):
                    raise ValueError(f"Notification service missing required method: {method}")

            self.notification_service = notification_service
            self.logger.debug(f"Notification service configured for {self.name}")

        except Exception as e:
            self.logger.error(f"Failed to configure notification service for {self.name}: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute notification operations based on the context and inputs.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            Notification operation result dict
        """
        if not self.notification_service:
            raise ValueError("Notification service not configured")

        operation = self.context.get("operation", "send_notification")

        if operation == "send_notification":
            channel = inputs.get("channel", "console")
            message = inputs.get("message", "Notification from AgentMap agent")
            recipient = inputs.get("recipient")

            success = self.notification_service.send_notification(channel, message, recipient)
            result = {"notification_sent": success, "channel": channel, "message": message}

        elif operation == "send_agent_notification":
            operation_name = self.context.get("operation_name", "Agent Operation")
            operation_result = self.context.get("operation_result", "Completed")
            channels = inputs.get("channels", ["console"])

            results = self.notification_service.send_agent_notification(
                self.name, operation_name, operation_result, channels
            )
            result = {"notifications_sent": results, "channels": list(results.keys())}

        elif operation == "get_sent_notifications":
            sent_notifications = self.notification_service.get_sent_notifications()
            result = {"sent_notifications": sent_notifications, "count": len(sent_notifications)}

        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.logger.info(f"NotificationAgent '{self.name}' completed {operation}")
        return result


class FileAgent(BaseAgent, FileServiceProtocol):
    """
    Example agent that demonstrates file service integration.

    This agent can perform file operations using the injected file service.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize file agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.file_service = None
        self.logger.debug(f"FileAgent '{name}' initialized")

    def configure_file_service(self, file_service: Any) -> None:
        """
        Configure the agent with a file service.

        Args:
            file_service: File service instance
        """
        try:
            if not file_service:
                raise ValueError("File service cannot be None")

            required_methods = ['save_file', 'read_file', 'list_files']
            for method in required_methods:
                if not hasattr(file_service, method):
                    raise ValueError(f"File service missing required method: {method}")

            self.file_service = file_service
            self.logger.debug(f"File service configured for {self.name}")

        except Exception as e:
            self.logger.error(f"Failed to configure file service for {self.name}: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute file operations based on the context and inputs.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            File operation result dict
        """
        if not self.file_service:
            raise ValueError("File service not configured")

        operation = self.context.get("operation", "save_output")

        if operation == "save_file":
            filename = inputs.get("filename")
            content = inputs.get("content", "")
            subfolder = inputs.get("subfolder")

            if not filename:
                raise ValueError("'filename' parameter is required for save_file operation")

            file_path = self.file_service.save_file(filename, content, subfolder)
            result = {"file_saved": True, "path": file_path, "filename": filename}

        elif operation == "read_file":
            filename = inputs.get("filename")
            subfolder = inputs.get("subfolder")

            if not filename:
                raise ValueError("'filename' parameter is required for read_file operation")

            content = self.file_service.read_file(filename, subfolder)
            result = {"file_read": True, "content": content, "filename": filename}

        elif operation == "list_files":
            subfolder = inputs.get("subfolder")

            files = self.file_service.list_files(subfolder)
            result = {"files": files, "count": len(files), "subfolder": subfolder}

        elif operation == "save_output":
            output_data = inputs.get("output_data", inputs)
            graph_name = inputs.get("graph_name")

            file_path = self.file_service.save_agent_output(self.name, output_data, graph_name)
            result = {"output_saved": True, "path": file_path}

        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.logger.info(f"FileAgent '{self.name}' completed {operation}")
        return result


class MultiServiceAgent(BaseAgent, FullServiceAgentProtocol):
    """
    Example agent that demonstrates multiple host service integration.

    This agent implements multiple protocols and can use database, email,
    and notification services in coordinated operations.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize multi-service agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.database_service = None
        self.email_service = None
        self.notification_service = None
        self.logger.debug(f"MultiServiceAgent '{name}' initialized")

    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service."""
        try:
            if not database_service:
                raise ValueError("Database service cannot be None")
            self.database_service = database_service
            self.logger.debug(f"Database service configured for {self.name}")
        except Exception as e:
            self.logger.error(f"Failed to configure database service for {self.name}: {e}")
            raise

    def configure_email_service(self, email_service: Any) -> None:
        """Configure email service."""
        try:
            if not email_service:
                raise ValueError("Email service cannot be None")
            self.email_service = email_service
            self.logger.debug(f"Email service configured for {self.name}")
        except Exception as e:
            self.logger.error(f"Failed to configure email service for {self.name}: {e}")
            raise

    def configure_notification_service(self, notification_service: Any) -> None:
        """Configure notification service."""
        try:
            if not notification_service:
                raise ValueError("Notification service cannot be None")
            self.notification_service = notification_service
            self.logger.debug(f"Notification service configured for {self.name}")
        except Exception as e:
            self.logger.error(f"Failed to configure notification service for {self.name}: {e}")
            raise

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute multi-service operations that coordinate between services.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            Coordinated operation result dict
        """
        operation = self.context.get("operation", "process_user_request")

        if operation == "process_user_request":
            result = self._process_user_request(inputs)

        elif operation == "generate_report":
            result = self._generate_report(inputs)

        elif operation == "handle_task_completion":
            result = self._handle_task_completion(inputs)

        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.logger.info(f"MultiServiceAgent '{self.name}' completed {operation}")
        return result

    def _process_user_request(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process a user request using multiple services."""
        user_id = self.context.get("user_id") or inputs.get("user_id")
        if user_id is not None:
            user_id = int(user_id)
        if not user_id:
            raise ValueError("user_id required for process_user_request")

        # Step 1: Get user data from database
        if self.database_service:
            users = self.database_service.get_users()
            user = next((u for u in users if u["id"] == user_id), None)
            if not user:
                raise ValueError(f"User {user_id} not found")

            tasks = self.database_service.get_tasks_for_user(user_id)
        else:
            raise ValueError("Database service not available")

        # Step 2: Create summary of user tasks
        summary = f"User {user['name']} has {len(tasks)} tasks"
        if tasks:
            completed_count = len([t for t in tasks if t['status'] == 'completed'])
            pending_count = len([t for t in tasks if t['status'] == 'pending'])
            summary = f"User {user['name']} has {len(tasks)} tasks: {completed_count} completed, {pending_count} pending"

        # Step 3: Send notifications
        if self.notification_service:
            self.notification_service.send_notification(
                "console",
                f"Processed request for user {user['name']} ({len(tasks)} tasks)",
                user["email"]
            )

        # Step 4: Log the operation
        if self.database_service:
            self.database_service.log_agent_operation(
                agent_name=self.name,
                operation="process_user_request",
                result=f"Processed {len(tasks)} tasks for user {user_id}",
            )

        return {
            "user": user,
            "tasks": tasks,
            "summary": summary,
            "processed_at": "2024-01-01T12:00:00Z"
        }

    def _generate_report(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a report using database and LLM services."""
        if not self.database_service:
            raise ValueError("Database service not available for report generation")

        users = self.database_service.get_users()
        all_tasks = self.database_service.execute_query("SELECT * FROM tasks")

        stats = {
            "total_users": len(users),
            "total_tasks": len(all_tasks),
            "completed_tasks": len([t for t in all_tasks if t["status"] == "completed"]),
            "pending_tasks": len([t for t in all_tasks if t["status"] == "pending"])
        }

        summary = f"Report generated: {stats['total_users']} users, {stats['total_tasks']} tasks"

        self.database_service.log_agent_operation(
            agent_name=self.name,
            operation="generate_report",
            result=f"Generated report with {stats['total_tasks']} tasks",
        )

        return {
            "statistics": stats,
            "summary": summary,
            "generated_at": "2024-01-01T12:00:00Z"
        }

    def _handle_task_completion(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task completion with multi-service coordination."""
        task_id = inputs.get("task_id")
        if not task_id:
            raise ValueError("task_id required for handle_task_completion")

        results = {}

        if self.database_service:
            self.database_service.log_agent_operation(
                agent_name=self.name,
                operation="handle_task_completion",
                result=f"Handled completion of task {task_id}",
            )
            results["database_logged"] = True

        if self.notification_service:
            success = self.notification_service.send_notification(
                "console",
                f"Task {task_id} has been completed",
                inputs.get("recipient")
            )
            results["notification_sent"] = success

        if self.email_service and inputs.get("send_email"):
            email_success = self.email_service.send_notification_email(
                inputs.get("email", "admin@example.com"),
                self.name,
                "Task Completion",
                f"Task {task_id} completed successfully"
            )
            results["email_sent"] = email_success

        return results


class RobustHostServiceAgent(BaseAgent, DatabaseServiceProtocol, EmailServiceProtocol):
    """
    Example agent demonstrating robust error handling with host services.

    This agent shows best practices for handling service failures and
    implementing graceful degradation when services are unavailable.
    """

    def __init__(self, name: str, prompt: str = "", context: Optional[Dict[str, Any]] = None,
                 logger=None, execution_tracking_service=None,
                 state_adapter_service=None, **kwargs):
        """Initialize robust host service agent."""
        super().__init__(name, prompt, context, logger,
                         execution_tracking_service=execution_tracking_service,
                         state_adapter_service=state_adapter_service, **kwargs)
        self.database_service = None
        self.email_service = None
        self._services_configured = []

    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service with validation."""
        try:
            if database_service and hasattr(database_service, 'execute_query'):
                self.database_service = database_service
                self._services_configured.append("database")
                self.logger.debug(f"Database service configured for {self.name}")
            else:
                self.logger.warning(f"Invalid database service for {self.name}")
        except Exception as e:
            self.logger.error(f"Database service configuration failed for {self.name}: {e}")

    def configure_email_service(self, email_service: Any) -> None:
        """Configure email service with validation."""
        try:
            if email_service and hasattr(email_service, 'send_email'):
                self.email_service = email_service
                self._services_configured.append("email")
                self.logger.debug(f"Email service configured for {self.name}")
            else:
                self.logger.warning(f"Invalid email service for {self.name}")
        except Exception as e:
            self.logger.error(f"Email service configuration failed for {self.name}: {e}")

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Execute operations with graceful degradation when services fail.

        Args:
            inputs: Dictionary of input values from Input_Fields

        Returns:
            Operation results with service status
        """
        results = {
            "services_available": self._services_configured.copy(),
            "operations_completed": [],
            "operations_failed": []
        }

        # Try database operation
        if "database" in self._services_configured:
            try:
                users = self.database_service.get_users()
                results["database_result"] = {"users": users, "count": len(users)}
                results["operations_completed"].append("database_query")
            except Exception as e:
                self.logger.error(f"Database operation failed: {e}")
                results["operations_failed"].append({"operation": "database_query", "error": str(e)})
        else:
            results["operations_failed"].append({"operation": "database_query", "error": "service_not_available"})

        # Try email operation
        if "email" in self._services_configured and inputs.get("send_notification"):
            try:
                success = self.email_service.send_email(
                    inputs.get("email", "admin@example.com"),
                    "Agent Operation Complete",
                    f"Agent {self.name} completed operations"
                )
                results["email_result"] = {"sent": success}
                results["operations_completed"].append("email_notification")
            except Exception as e:
                self.logger.error(f"Email operation failed: {e}")
                results["operations_failed"].append({"operation": "email_notification", "error": str(e)})

        results["status"] = "completed_with_degradation" if results["operations_failed"] else "completed"
        results["agent_name"] = self.name

        return results
