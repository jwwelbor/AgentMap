# test_registration.py
from agentmap.agents import get_agent_class

# Try to get the agent classes
file_reader = get_agent_class("file_reader")
file_writer = get_agent_class("file_writer")

# Print the results
print(f"FileReaderAgent class: {file_reader}")
print(f"FileWriterAgent class: {file_writer}")

# Test instantiation
if file_reader and file_writer:
    reader = file_reader("TestReader", "test.txt")
    writer = file_writer("TestWriter", "test.txt")
    print("Successfully instantiated agents!")