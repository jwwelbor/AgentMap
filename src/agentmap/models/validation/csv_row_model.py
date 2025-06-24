# src/agentmap/models/validation/models.py
"""
Pydantic models for validating CSV and configuration files.
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CSVRowModel(BaseModel):
    """Pydantic model for validating individual CSV rows."""

    # Required fields
    GraphName: str = Field(min_length=1, description="Name of the graph")
    Node: str = Field(min_length=1, description="Name of the node")

    # Optional core fields
    AgentType: Optional[str] = Field(default=None, description="Type of agent")
    Prompt: Optional[str] = Field(
        default=None, description="Agent prompt or instructions"
    )
    Description: Optional[str] = Field(default=None, description="Node description")

    # Input/Output fields
    Input_Fields: Optional[str] = Field(
        default=None, description="Pipe-separated input field names"
    )
    Output_Field: Optional[str] = Field(default=None, description="Output field name")
    Context: Optional[str] = Field(
        default=None, description="Additional context for the agent"
    )

    # Routing fields
    Edge: Optional[str] = Field(default=None, description="Direct edge target")
    Success_Next: Optional[str] = Field(
        default=None, description="Target node on success"
    )
    Failure_Next: Optional[str] = Field(
        default=None, description="Target node on failure"
    )

    @field_validator("GraphName", "Node")
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        """Validate required fields are not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or just whitespace")
        return v.strip()

    @field_validator("Input_Fields")
    @classmethod
    def validate_input_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate input fields format (pipe-separated)."""
        if v is None:
            return v

        # Split by pipe and validate each field name
        fields = [f.strip() for f in v.split("|") if f.strip()]

        # Check for valid field names (basic validation)
        for field in fields:
            if not field.replace("_", "").replace("-", "").isalnum():
                raise ValueError(
                    f"Invalid field name: '{field}'. Use alphanumeric characters, underscore, or dash only."
                )

        return "|".join(fields)

    @field_validator("Output_Field")
    @classmethod
    def validate_output_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate output field name."""
        if v is None:
            return v

        v = v.strip()
        if v and not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"Invalid output field name: '{v}'. Use alphanumeric characters, underscore, or dash only."
            )

        return v

    @model_validator(mode="after")
    def validate_routing_logic(self) -> "CSVRowModel":
        """Validate routing logic constraints."""
        # Check for conflicting edge definitions
        has_direct_edge = bool(self.Edge)
        has_conditional_edges = bool(self.Success_Next or self.Failure_Next)

        if has_direct_edge and has_conditional_edges:
            raise ValueError(
                "Cannot have both Edge and Success/Failure_Next defined. "
                "Use either direct routing (Edge) or conditional routing (Success/Failure_Next)."
            )

        return self
