---
sidebar_position: 3
title: Your First Multi-Agent Workflow
description: Build a real-world document analysis workflow with multiple AI agents collaborating. Takes 15 minutes to complete.
keywords: [multi-agent workflow, document analysis, AI collaboration, tutorial, practical example]
---

# Your First Multi-Agent Workflow

Now that you've run a simple workflow, let's build something practical: a **document analysis system** where multiple AI agents collaborate to analyze and summarize documents.

## ⚡ Progress Tracker

<div style={{backgroundColor: '#f8f9fa', padding: '1rem', borderRadius: '0.5rem', marginBottom: '2rem'}}>

**Total Time: ~15 minutes**

- [ ] **Step 1:** Understand the workflow design (2 min)
- [ ] **Step 2:** Create the workflow CSV (5 min)
- [ ] **Step 3:** Prepare sample data (3 min)
- [ ] **Step 4:** Run and test (3 min)
- [ ] **Step 5:** Understand what happened (2 min)

</div>

## Step 1: Workflow Design

We'll build a **Personal Goal Analyzer** that:
1. **Collects** a personal goal from the user
2. **Analyzes** it using AI to provide insights and action steps
3. **Saves** the analysis to a CSV file for tracking
4. **Thanks** the user and shows next steps

This demonstrates:
- ✅ **User interaction** (input agent)
- ✅ **AI processing** (LLM agent) 
- ✅ **Data persistence** (CSV writer agent)
- ✅ **Error handling** (error handler)
- ✅ **Data flow** between agents

*Expected time: 2 minutes*

## Step 2: Create the Workflow

Create a file called `personal_goals.csv`:

```csv
graph_name,node_name,description,agent_type,next_node,error_node,input_fields,output_field,prompt,context
PersonalGoals,GetGoal,Collect user's personal goal,input,AnalyzeGoal,ErrorHandler,,goal,What personal goal would you like to work on this year? Please be specific:,
PersonalGoals,AnalyzeGoal,AI analysis of the goal,llm,SaveGoal,ErrorHandler,goal,analysis,"You are a personal development coach. Analyze this goal and provide: 1) Why this goal is valuable 2) Three specific action steps 3) One potential challenge and how to overcome it. Goal: {goal}","{""provider"": ""anthropic"", ""model"": ""claude-3-5-sonnet-20241022"", ""temperature"": 0.3}"
PersonalGoals,SaveGoal,Save goal and analysis to CSV,csv_writer,ThankUser,ErrorHandler,"goal,analysis",save_result,personal_goals.csv,"{""format"": ""records"", ""mode"": ""append""}"
PersonalGoals,ThankUser,Thank user and show summary,echo,End,,save_result,final_message,Thank you! Your goal and AI analysis have been saved. You can view your goals database at personal_goals.csv,
PersonalGoals,ErrorHandler,Handle any errors,echo,End,,error,error_message,Sorry there was an error: {error},
PersonalGoals,End,Workflow complete,echo,,,final_message,completion,Workflow completed successfully!,
```

### 🔍 Understanding the Workflow

Let's break down what each agent does:

| Agent | Type | Purpose | Input | Output |
|-------|------|---------|--------|---------|
| `GetGoal` | `input` | Prompts user for their goal | - | `goal` |
| `AnalyzeGoal` | `llm` | AI analyzes the goal | `goal` | `analysis` |
| `SaveGoal` | `csv_writer` | Saves to CSV file | `goal`, `analysis` | `save_result` |
| `ThankUser` | `echo` | Shows completion message | `save_result` | `final_message` |
| `ErrorHandler` | `echo` | Handles any errors | `error` | `error_message` |
| `End` | `echo` | Workflow completion | `final_message` | `completion` |

**Data Flow**: `goal` → `analysis` → `save_result` → `final_message` → `completion`

*Expected time: 5 minutes*

## Step 3: Prepare Sample Data

No preparation needed! The CSV writer will automatically create the `personal_goals.csv` file when it runs.

*Expected time: 3 minutes*

## Step 4: Run the Workflow

```bash
agentmap run --csv personal_goals.csv --graph PersonalGoals
```

**Sample interaction**:
```
What personal goal would you like to work on this year? Please be specific:
> Learn to play piano and perform one song for my family

[AI processes the goal...]

Thank you! Your goal and AI analysis have been saved. 
You can view your goals database at data/personal_goals.csv

Workflow completed successfully!
```

*Expected time: 3 minutes*

## Step 5: Check the Results

Look at the generated file:

```bash
cat personal_goals.csv
```

You should see:
```csv
goal,analysis
"Learn to play piano and perform one song for my family","**Why this goal is valuable:**
Learning piano enhances cognitive function, provides emotional outlet, and creates meaningful family moments...

**Three specific action steps:**
1. Start with basic finger exercises and simple scales (15 mins daily)
2. Choose one meaningful song and break it into small sections
3. Schedule weekly practice sessions and monthly family mini-performances

**Potential challenge and solution:**
Challenge: Finding consistent practice time with busy schedule
Solution: Set same time daily (like morning coffee) and use apps for 5-minute micro-sessions when full practice isn't possible"
```

*Expected time: 2 minutes*

## 🎯 What You Just Built

**Congratulations!** You created a sophisticated multi-agent system that:

✅ **Handles user interaction** - Collects input with validation  
✅ **Uses AI reasoning** - Leverages Claude for smart analysis  
✅ **Persists data** - Saves results to structured CSV  
✅ **Provides feedback** - Clear user experience  
✅ **Handles errors** - Graceful failure management  
✅ **Scales easily** - Can process multiple goals over time  

## 🔍 Key Concepts Demonstrated

### Agent Chaining
```csv
GetGoal → AnalyzeGoal → SaveGoal → ThankUser → End
```
Each agent passes its output to the next agent's input.

### Error Handling
```csv
error_node,ErrorHandler
```
Any agent failure routes to the error handler.

### Service Integration
```csv
agent_type,llm
context,"{""provider"": ""anthropic""}"
```
Agents automatically get the services they need.

### Data Persistence
```csv
agent_type,csv_writer
prompt,data/personal_goals.csv
```
Workflows can save data for later use.

## 🚀 Next Steps

You now understand multi-agent workflows! Here are your next learning paths:

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', margin: '2rem 0'}}>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>🎓 Structured Learning</strong><br/>
  <a href="/docs/learning/basic-agents">Basic Agents Lesson →</a><br/>
  <em>Deep dive into agent types and capabilities</em>
</div>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>🔧 Custom Agents</strong><br/>
  <a href="/docs/learning/custom-agent">Custom Agent Development →</a><br/>
  <em>Build your own specialized agents</em>
</div>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>⚙️ Production Setup</strong><br/>
  <a href="./installation">Installation Guide →</a><br/>
  <em>Multiple providers, monitoring, deployment</em>
</div>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>📚 Agent Library</strong><br/>
  <a href="/docs/agents/built-in-agents">Built-in Agents →</a><br/>
  <em>Discover all available agent types</em>
</div>

</div>

## 💡 Pro Tips

- **Start with templates**: Use existing workflows as starting points
- **Test incrementally**: Build one agent at a time, then connect them
- **Use descriptive names**: `AnalyzeGoal` is better than `Step2`
- **Add error handling**: Always include error nodes for production workflows
- **Think about data flow**: Plan what data flows between agents

## 🛠️ Troubleshooting

<details>
<summary><strong>Issue: "LLM agent failed"</strong></summary>

**Check your API key**:
```bash
echo $ANTHROPIC_API_KEY
# or
echo $OPENAI_API_KEY
```

**Update the context** to use your available provider:
```csv
context,"{""provider"": ""openai"", ""model"": ""gpt-4""}"
```
</details>

<details>
<summary><strong>Issue: "CSV writer failed"</strong></summary>

**Verify file path** in your CSV:
```csv
prompt,personal_goals.csv
```
</details>

<details>
<summary><strong>Issue: "Graph not found"</strong></summary>

**Check the graph_name** matches exactly:
```bash
agentmap run --csv personal_goals.csv --graph PersonalGoals
```
All instances of `graph_name` in your CSV must be identical.
</details>

---

**Great job!** You've mastered the fundamentals of multi-agent workflows. You're ready to build sophisticated AI systems with AgentMap.

**Need help?** Join the [GitHub discussions](https://github.com/jwwelbor/AgentMap/discussions) or check out more [examples](/docs/configuration/examples).
