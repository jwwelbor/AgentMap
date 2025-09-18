---
sidebar_position: 2
title: Quick Start (5 Minutes)
description: Install AgentMap and run your first AI workflow in 5 minutes. Minimal setup to get started immediately.
keywords: [quick start, installation, first workflow, 5 minutes, setup]
---

# Quick Start (5 Minutes)

Get AgentMap running in 5 minutes with this streamlined guide.

## ⚡ Progress Tracker

<div style={{backgroundColor: '#f8f9fa', padding: '1rem', borderRadius: '0.5rem', marginBottom: '2rem'}}>

**Total Time: ~5 minutes**

- [ ] **Step 1:** Install (30 seconds)
- [ ] **Step 2:** Set API Key (30 seconds) 
- [ ] **Step 3:** Create workflow (2 minutes)
- [ ] **Step 4:** Run workflow (30 seconds)
- [ ] **Step 5:** Verify success (30 seconds)

</div>

## Step 1: Install AgentMap

```bash
pip install agentmap
```

*Expected time: 30 seconds*

## Step 2: Set Your API Key

Pick **one** provider and set your API key:

```bash
# Option A: OpenAI (recommended for beginners)
export OPENAI_API_KEY="your-api-key-here"

# Option B: Anthropic (Claude)
export ANTHROPIC_API_KEY="your-api-key-here"

# Option C: Google (Gemini)  
export GOOGLE_API_KEY="your-api-key-here"
```

:::tip Getting API Keys
- **OpenAI**: Get key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Anthropic**: Get key from [console.anthropic.com](https://console.anthropic.com/)
- **Google**: Get key from [ai.google.dev](https://ai.google.dev/)
:::

*Expected time: 30 seconds*

## Step 3: Create Your First Workflow

Create a file called `hello_world.csv`:

```csv
graph_name,node_name,agent_type,next_node,on_failure,prompt,input_fields,output_field
HelloWorld,Start,input,PrintResult,HandleError,"Hello! What is your name?",,name
HelloWorld,PrintResult,echo,,,"Hello {name}. Welcome to AgentMap!",name,result
HelloWorld,HandleError,echo,,,Error occurred
```

*Expected time: 2 minutes*

## Step 4: Run Your Workflow

**✨ New Simplified Syntax (Recommended):**
```bash
agentmap run --csv hello_world.csv
```

**Traditional Syntax (Still Supported):**
```bash
agentmap run --csv hello_world.csv --graph HelloWorld
```

**Custom Graph Names:**
```bash
# Override graph name using :: syntax
agentmap run --csv hello_world.csv::MyCustomBot
```

*Expected time: 30 seconds*

## Step 5: Success! 🎉

You should see:
```
Hello! What is your name?
> [Enter your name, e.g., "Alex"]
Hello Alex. Welcome to AgentMap!
```

*Expected time: 30 seconds*

---

## ⚠️ Quick Troubleshooting

<details>
<summary><strong>Issue: "No LLM providers available"</strong></summary>

**Problem**: API key not set correctly.

**Solution**:
```bash
# Check if your key is set
echo $OPENAI_API_KEY

# If empty, set it properly:
export OPENAI_API_KEY="your-actual-key-here"
```
</details>

<details>
<summary><strong>Issue: "Module not found"</strong></summary>

**Problem**: AgentMap not installed properly.

**Solution**:
```bash
# Reinstall with verbose output
pip install --upgrade agentmap
agentmap diagnose
```
</details>

<details>
<summary><strong>Issue: "CSV parsing error"</strong></summary>

**Problem**: CSV file format issue.

**Solution**: Copy the exact CSV content from Step 3 above. Ensure no extra spaces or special characters.
</details>

---

## ✅ You're Ready!

**Congratulations!** You just:
- ✅ Installed AgentMap
- ✅ Set up AI provider access  
- ✅ Created a multi-agent workflow in CSV
- ✅ Ran your first AI workflow

## 🚀 Next Steps (Choose Your Path)

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', margin: '2rem 0'}}>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>🏗️ Build Your First Real Workflow</strong><br/>
  <a href="./first-workflow">First Workflow Guide →</a><br/>
  <em>15-minute tutorial: Document analysis workflow</em>
</div>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>📚 Learn Step by Step</strong><br/>
  <a href="/docs/learning/basic-agents">Learning Path →</a><br/>
  <em>Progressive lessons from basic to advanced</em>
</div>

<div style={{border: '1px solid #e1e4e8', padding: '1rem', borderRadius: '0.5rem'}}>
  <strong>🔧 Advanced Setup</strong><br/>
  <a href="./installation">Installation Guide →</a><br/>
  <em>Multiple providers, production config</em>
</div>

</div>

## 💡 Pro Tips

- **Start Simple**: Master single-agent workflows before building complex chains
- **Test Incrementally**: Add one agent at a time when building larger workflows  
- **Use Templates**: Check out [examples](/docs/configuration/examples) for common patterns
- **Get Help**: Join discussions at [GitHub](https://github.com/jwwelbor/AgentMap/discussions)

---

**Having issues?** See the full [Installation Guide](./installation) for detailed troubleshooting.
