# Domain Model Principles: Keep Models Simple!

## 🚨 **CRITICAL PRINCIPLE: Models Are Data Containers Only**

**Domain models in AgentMap are pure data containers with minimal behavior. All business logic belongs in services.**

## ✅ **What SHOULD Go in Domain Models**

### **Data Properties**
- Simple properties and fields
- Basic initialization
- Type hints and validation

### **Data Access Methods**
- Simple getters/setters
- Basic property queries (e.g., `has_conditional_routing()`)
- String representation (`__repr__`)

### **Data Storage Methods**
- Simple data manipulation (e.g., `add_edge()` for storing relationships)
- No complex calculations or business rules

## ❌ **What SHOULD NOT Go in Domain Models**

### **Business Logic**
- Complex validation rules → ValidationService
- Graph traversal → GraphAnalysisService
- Parsing logic → GraphBuilderService
- Routing decisions → GraphAssemblerService

### **Cross-Entity Operations**
- Operations involving multiple models
- Calculations spanning entities
- Complex state management

### **External Dependencies**
- Service calls
- File I/O
- Network operations
- Complex computations

## 📋 **AgentMap-Specific Examples**

### **Node Model (Correct - Simple Data Container)**
```python
class Node:
    def __init__(self, name, context=None, agent_type=None, ...):
        self.name = name
        self.context = context
        # ... other properties
        self.edges = {}
    
    def add_edge(self, condition, target):
        """Simple data storage"""
        self.edges[condition] = target
    
    def has_conditional_routing(self):
        """Simple data query"""
        return "success" in self.edges or "failure" in self.edges
```

### **What Belongs in Services Instead**
- **GraphBuilderService**: CSV parsing, node creation, edge connection
- **GraphValidationService**: Complex validation rules, graph consistency checks
- **GraphAnalysisService**: Traversal, reachability analysis, cycle detection
- **GraphAssemblerService**: LangGraph construction, routing logic

## 🎯 **Current AgentMap Architecture**

### **Existing Separation (Preserve This!)**
- **GraphBuilder**: Parses CSV → Creates Node objects → Calls `node.add_edge()`
- **GraphAssembler**: Takes nodes → Builds executable graphs → Handles routing logic
- **Node**: Simple data container for properties and edges

### **New Services Should Follow Same Pattern**
- **GraphBuilderService**: Wraps GraphBuilder, converts to domain models
- **CompilationService**: Wraps compilation logic, coordinates with other services
- **GraphRunnerService**: Orchestrates execution, tracks results

## 📝 **Testing Strategy for Models**

### **Model Tests Should Focus On:**
- Property initialization
- Data storage and retrieval
- Simple behavior verification
- Type safety

### **Model Tests Should NOT Test:**
- Complex business logic (that's service territory)
- Cross-model operations
- External integrations
- Complex calculations

## 🚨 **Red Flags: When You're Violating This Principle**

### **If You're Adding to Models:**
- Methods with complex parameters
- Methods calling other services
- Methods with complex business rules
- Methods doing calculations across multiple entities
- Methods involving external resources

### **Ask Yourself:**
- "Is this intrinsic to the entity's data?"
- "Could this logic be reused by other services?"
- "Does this involve coordination between entities?"

**If ANY answer is "yes" → Put it in a service!**

## 🎯 **Reminder for Future Development**

**When working on AgentMap, always ask:**
1. **"Is this just data storage/access?"** → Model
2. **"Is this business logic or coordination?"** → Service
3. **"Does this involve multiple entities?"** → Service
4. **"Could this be complex or change often?"** → Service

## 📖 **Key Phrase for Future Sessions**

**Use this phrase to maintain focus:**

> "Remember: AgentMap models are simple data containers. All business logic belongs in services, following the existing GraphBuilder/GraphAssembler pattern."

---

**This principle ensures clean architecture, testability, and maintainability throughout the AgentMap migration.**
