import React, { useState, useMemo, useCallback, useEffect } from 'react';
import styles from './WorkflowVisualizer.module.css';

interface ParsedNode {
  name: string;
  graphName: string;
  context: string;
  agentType: string;
  successNext: string;
  failureNext: string;
  inputFields: string;
  outputField: string;
  prompt: string;
  description: string;
}

interface ParsedWorkflow {
  nodes: ParsedNode[];
  connections: Array<{
    from: string;
    to: string;
    type: 'success' | 'failure';
  }>;
  graphName: string;
  errors: string[];
}

interface WorkflowTemplate {
  name: string;
  description: string;
  csv: string;
  category: string;
}

const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    name: 'Simple Weather Bot',
    description: 'Basic weather information retrieval workflow',
    category: 'Beginner',
    csv: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
WeatherBot,GetLocation,,Get user location,input,FetchWeather,Error,,location,Enter your city:,Get user location
WeatherBot,FetchWeather,,Fetch weather data,llm,DisplayWeather,Error,location,weather_data,Get current weather for {location},Fetch weather information
WeatherBot,DisplayWeather,,Display weather info,echo,End,Error,weather_data,result,,Display weather results
WeatherBot,Error,,Handle errors,echo,End,,error,error_message,,Display error message
WeatherBot,End,,Workflow complete,echo,,,result|error_message,output,,End of workflow`
  },
  {
    name: 'Data Processing Pipeline',
    description: 'CSV data processing and analysis workflow',
    category: 'Intermediate',
    csv: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DataPipeline,LoadData,,Load CSV data,csv_reader,ValidateData,HandleError,file_path,raw_data,,Load data from CSV file
DataPipeline,ValidateData,,Validate data quality,custom:DataValidatorAgent,ProcessData,HandleError,raw_data,validated_data,,Validate data integrity
DataPipeline,ProcessData,,Process and analyze data,custom:DataProcessorAgent,GenerateReport,HandleError,validated_data,processed_data,,Analyze and transform data
DataPipeline,GenerateReport,,Generate analysis report,llm,SaveResults,HandleError,processed_data,report,Generate a summary report of this data: {processed_data},Create analysis report
DataPipeline,SaveResults,,Save processed results,csv_writer,End,HandleError,report|processed_data,save_result,,Save results to file
DataPipeline,HandleError,,Handle processing errors,echo,End,,error,error_message,,Display error information
DataPipeline,End,,Pipeline complete,echo,,,save_result|error_message,output,,End of pipeline`
  },
  {
    name: 'Customer Support Bot',
    description: 'Multi-intent customer service workflow',
    category: 'Advanced',
    csv: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
SupportBot,GetMessage,,Get customer message,input,ClassifyIntent,Error,,customer_message,What can I help you with today?,Get customer inquiry
SupportBot,ClassifyIntent,,Classify customer intent,llm,RouteToHandler,Error,customer_message,intent,Classify this customer message into one of: billing, technical, general: {customer_message},Determine customer intent
SupportBot,RouteToHandler,,Route to appropriate handler,branching,HandleBilling|HandleTechnical|HandleGeneral,Error,intent,routing_decision,,Route based on intent classification
SupportBot,HandleBilling,,Handle billing inquiries,llm,CollectFeedback,Error,customer_message,billing_response,Handle this billing inquiry professionally: {customer_message},Process billing request
SupportBot,HandleTechnical,,Handle technical support,llm,CollectFeedback,Error,customer_message,tech_response,Provide technical support for: {customer_message},Process technical request
SupportBot,HandleGeneral,,Handle general inquiries,llm,CollectFeedback,Error,customer_message,general_response,Provide helpful information for: {customer_message},Process general inquiry
SupportBot,CollectFeedback,,Collect customer feedback,input,End,Error,billing_response|tech_response|general_response,feedback,How would you rate this interaction (1-5)?,Get customer satisfaction
SupportBot,Error,,Handle errors gracefully,echo,End,,error,error_message,,Display error message
SupportBot,End,,Complete interaction,echo,,,feedback,output,,End customer interaction`
  },
  {
    name: 'API Integration Pipeline',
    description: 'Multi-source data integration workflow',
    category: 'Expert',
    csv: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
APIIntegration,LoadConfig,,Load API configuration,custom:ConfigLoaderAgent,FetchWeatherData,HandleError,config_path,api_config,,Load API keys and settings
APIIntegration,FetchWeatherData,,Fetch weather data,custom:WeatherAPIAgent,FetchStockData,HandleAPIError,api_config,weather_data,,Get current weather data
APIIntegration,FetchStockData,,Fetch stock market data,custom:StockAPIAgent,FetchNewsData,HandleAPIError,api_config,stock_data,,Get stock market information
APIIntegration,FetchNewsData,,Fetch latest news,custom:NewsAPIAgent,MergeData,HandleAPIError,api_config,news_data,,Get current news articles
APIIntegration,MergeData,,Combine all data sources,custom:DataMergerAgent,AnalyzeData,HandleError,weather_data|stock_data|news_data,merged_data,,Combine data from all sources
APIIntegration,AnalyzeData,,Generate insights,llm,StoreResults,HandleError,merged_data,analysis,Analyze this integrated data and provide insights: {merged_data},Generate data insights
APIIntegration,StoreResults,,Save results,json_writer,SendNotification,HandleError,merged_data|analysis,storage_result,,Store processed data
APIIntegration,SendNotification,,Send completion alert,custom:NotificationAgent,End,HandleError,storage_result,notification_result,,Notify completion
APIIntegration,HandleAPIError,,Handle API failures,custom:FallbackDataAgent,MergeData,HandleError,error,fallback_data,,Use sample data when APIs fail
APIIntegration,HandleError,,Handle critical errors,echo,End,,error,error_message,,Display error information
APIIntegration,End,,Integration complete,echo,,,notification_result|error_message,output,,End integration pipeline`
  }
];

const AGENT_TYPE_COLORS = {
  // Core agents
  'input': '#4CAF50',
  'echo': '#4CAF50', 
  'default': '#4CAF50',
  'branching': '#4CAF50',
  'success': '#4CAF50',
  'failure': '#4CAF50',
  
  // LLM agents
  'llm': '#2196F3',
  'openai': '#2196F3',
  'gpt': '#2196F3',
  'claude': '#2196F3',
  'gemini': '#2196F3',
  
  // Storage agents
  'csv_reader': '#FF9800',
  'csv_writer': '#FF9800',
  'json_reader': '#FF9800', 
  'json_writer': '#FF9800',
  'vector_reader': '#FF9800',
  'vector_writer': '#FF9800',
  
  // File agents
  'file_reader': '#9C27B0',
  'file_writer': '#9C27B0',
  
  // Custom agents
  'custom': '#607D8B',
  
  // Default fallback
  'unknown': '#757575'
};

export default function WorkflowVisualizer(): JSX.Element {
  const [csvInput, setCsvInput] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [showErrors, setShowErrors] = useState(true);
  const [exportFormat, setExportFormat] = useState<'svg' | 'png'>('svg');
  const [isExporting, setIsExporting] = useState(false);

  // Parse CSV and generate workflow data
  const parsedWorkflow = useMemo(() => {
    return parseCSVToWorkflow(csvInput);
  }, [csvInput]);

  // Generate Mermaid diagram
  const mermaidDiagram = useMemo(() => {
    return generateMermaidDiagram(parsedWorkflow);
  }, [parsedWorkflow]);

  // Load template
  const loadTemplate = useCallback((templateName: string) => {
    const template = WORKFLOW_TEMPLATES.find(t => t.name === templateName);
    if (template) {
      setCsvInput(template.csv);
      setSelectedTemplate(templateName);
    }
  }, []);

  // Download CSV file
  const downloadCSV = useCallback(() => {
    if (!csvInput.trim()) return;
    
    const blob = new Blob([csvInput], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${parsedWorkflow.graphName || 'workflow'}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [csvInput, parsedWorkflow.graphName]);

  // Copy to clipboard
  const copyToClipboard = useCallback(async (text: string, type: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      // Could add toast notification here
      console.log(`${type} copied to clipboard`);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, []);

  // Export diagram
  const exportDiagram = useCallback(async () => {
    setIsExporting(true);
    try {
      // This would integrate with mermaid.js to export
      // For now, we'll copy the mermaid code
      await copyToClipboard(mermaidDiagram, 'Mermaid diagram');
      console.log('Diagram exported successfully');
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  }, [mermaidDiagram, copyToClipboard]);

  // Effect to render Mermaid diagram
  useEffect(() => {
    const renderMermaid = async () => {
      try {
        // Only run in browser environment
        if (typeof window === 'undefined') return;
        
        // Import mermaid dynamically to avoid SSR issues
        const mermaid = (await import('mermaid')).default;
        
        mermaid.initialize({
          startOnLoad: false,
          theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'default',
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
            curve: 'basis'
          },
          securityLevel: 'loose'
        });

        const element = document.getElementById('mermaid-diagram');
        if (element && mermaidDiagram) {
          try {
            // Clear previous content
            element.innerHTML = '';
            
            // Create a unique ID for this diagram
            const diagramId = `mermaid-${Date.now()}`;
            
            // Render the diagram
            const { svg } = await mermaid.render(diagramId, mermaidDiagram);
            element.innerHTML = svg;
          } catch (renderError) {
            console.error('Mermaid render error:', renderError);
            element.innerHTML = `<div class="${styles.errorContent}">Error rendering diagram: ${renderError.message}</div>`;
          }
        }
      } catch (err) {
        console.error('Mermaid loading failed:', err);
        const element = document.getElementById('mermaid-diagram');
        if (element) {
          element.innerHTML = `<div class="${styles.errorContent}">Failed to load diagram renderer</div>`;
        }
      }
    };

    if (mermaidDiagram && typeof window !== 'undefined') {
      renderMermaid();
    }
  }, [mermaidDiagram]);

  return (
    <div className={styles.workflowVisualizer}>
      <div className={styles.header}>
        <h1>🔄 CSV Workflow Visualizer</h1>
        <p>Convert your AgentMap CSV workflows into interactive visual diagrams</p>
      </div>

      <div className={styles.content}>
        <div className={styles.inputPanel}>
          <div className={styles.templateSelector}>
            <label htmlFor="template-select">Quick Start Templates:</label>
            <select
              id="template-select"
              value={selectedTemplate}
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                if (e.target.value) loadTemplate(e.target.value);
              }}
              className={styles.templateSelect}
            >
              <option value="">Choose a template...</option>
              {WORKFLOW_TEMPLATES.map(template => (
                <option key={template.name} value={template.name}>
                  {template.name} ({template.category})
                </option>
              ))}
            </select>
          </div>

          <div className={styles.csvEditor}>
            <div className={styles.editorHeader}>
              <label htmlFor="csv-input">CSV Workflow Definition:</label>
              <div className={styles.editorControls}>
                <button
                  onClick={() => copyToClipboard(csvInput, 'CSV')}
                  className={styles.controlButton}
                  disabled={!csvInput}
                  title="Copy CSV to clipboard"
                >
                  📋 Copy CSV
                </button>
                <button
                  onClick={downloadCSV}
                  className={styles.controlButton}
                  disabled={!csvInput}
                  title="Download CSV file"
                >
                  💾 Download
                </button>
                <button
                  onClick={() => setCsvInput('')}
                  className={styles.controlButton}
                  disabled={!csvInput}
                  title="Clear editor"
                >
                  🗑️ Clear
                </button>
              </div>
            </div>
            
            <textarea
              id="csv-input"
              value={csvInput}
              onChange={(e) => setCsvInput(e.target.value)}
              placeholder="Paste your AgentMap CSV workflow here, or select a template above..."
              className={styles.csvTextarea}
              rows={12}
            />

            {parsedWorkflow.errors.length > 0 && showErrors && (
              <div className={styles.errorPanel}>
                <div className={styles.errorHeader}>
                  <span>⚠️ CSV Parsing Errors:</span>
                  <button
                    onClick={() => setShowErrors(false)}
                    className={styles.dismissButton}
                  >
                    ✕
                  </button>
                </div>
                <ul className={styles.errorList}>
                  {parsedWorkflow.errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        <div className={styles.visualPanel}>
          <div className={styles.diagramHeader}>
            <h3>📊 Workflow Diagram</h3>
            <div className={styles.diagramControls}>
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as 'svg' | 'png')}
                className={styles.formatSelect}
              >
                <option value="svg">SVG</option>
                <option value="png">PNG</option>
              </select>
              <button
                onClick={exportDiagram}
                className={styles.exportButton}
                disabled={!mermaidDiagram || isExporting}
                title="Export diagram"
              >
                {isExporting ? '⏳ Exporting...' : `💾 Export ${exportFormat.toUpperCase()}`}
              </button>
              <button
                onClick={() => copyToClipboard(mermaidDiagram, 'Mermaid code')}
                className={styles.controlButton}
                disabled={!mermaidDiagram}
                title="Copy Mermaid code"
              >
                📋 Copy Code
              </button>
            </div>
          </div>

          <div className={styles.diagramContainer}>
            {mermaidDiagram ? (
              <div id="mermaid-diagram" className={styles.mermaidDiagram}>
                {/* Mermaid diagram will be rendered here */}
                <div className={styles.fallbackDiagram}>
                  <pre className={styles.mermaidCode}>{mermaidDiagram}</pre>
                </div>
              </div>
            ) : (
              <div className={styles.emptyDiagram}>
                <div className={styles.emptyContent}>
                  <h4>🎯 No workflow to display</h4>
                  <p>Enter CSV data above or select a template to see your workflow visualization</p>
                </div>
              </div>
            )}
          </div>

          {parsedWorkflow.nodes.length > 0 && (
            <div className={styles.workflowStats}>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Nodes:</span>
                <span className={styles.statValue}>{parsedWorkflow.nodes.length}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Connections:</span>
                <span className={styles.statValue}>{parsedWorkflow.connections.length}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Graph:</span>
                <span className={styles.statValue}>{parsedWorkflow.graphName || 'Unknown'}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className={styles.legend}>
        <h4>🎨 Agent Type Colors</h4>
        <div className={styles.colorLegend}>
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>Core Agents:</span>
            <span className={styles.colorDot} style={{ backgroundColor: AGENT_TYPE_COLORS.input }}></span>
            <span>Input/Echo/Default</span>
          </div>
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>LLM Agents:</span>
            <span className={styles.colorDot} style={{ backgroundColor: AGENT_TYPE_COLORS.llm }}></span>
            <span>LLM/GPT/Claude</span>
          </div>
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>Storage:</span>
            <span className={styles.colorDot} style={{ backgroundColor: AGENT_TYPE_COLORS.csv_reader }}></span>
            <span>CSV/JSON/Vector</span>
          </div>
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>File Agents:</span>
            <span className={styles.colorDot} style={{ backgroundColor: AGENT_TYPE_COLORS.file_reader }}></span>
            <span>File Read/Write</span>
          </div>
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>Custom:</span>
            <span className={styles.colorDot} style={{ backgroundColor: AGENT_TYPE_COLORS.custom }}></span>
            <span>Custom Agents</span>
          </div>
        </div>
      </div>

      <div className={styles.help}>
        <h4>💡 How to Use</h4>
        <ol>
          <li><strong>Start with a template:</strong> Choose from our pre-built examples above</li>
          <li><strong>Edit the CSV:</strong> Modify the workflow definition in the text area</li>
          <li><strong>See live updates:</strong> The diagram updates automatically as you type</li>
          <li><strong>Export your work:</strong> Copy the CSV or export the diagram as SVG/PNG</li>
          <li><strong>Fix errors:</strong> Check the error panel for CSV parsing issues</li>
        </ol>
        <p>
          Learn more about AgentMap CSV format in our{' '}
          <a href="/docs/guides/csv-format" target="_blank" rel="noopener noreferrer">
            CSV Format Guide
          </a>
        </p>
      </div>
    </div>
  );
}

// Helper function to parse CSV into workflow structure
function parseCSVToWorkflow(csvText: string): ParsedWorkflow {
  const lines = csvText.trim().split('\n');
  const errors: string[] = [];
  const nodes: ParsedNode[] = [];
  const connections: Array<{ from: string; to: string; type: 'success' | 'failure' }> = [];
  let graphName = '';

  if (!csvText.trim()) {
    return { nodes, connections, graphName, errors };
  }

  // Parse header
  if (lines.length === 0) {
    errors.push('CSV is empty');
    return { nodes, connections, graphName, errors };
  }

  const headerLine = lines[0];
  const expectedHeaders = [
    'GraphName', 'Node', 'Edge', 'Context', 'AgentType', 
    'Success_Next', 'Failure_Next', 'Input_Fields', 'Output_Field', 'Prompt', 'Description'
  ];

  const headers = headerLine.split(',').map(h => h.trim());
  
  // Check for required headers
  const missingHeaders = expectedHeaders.filter(h => !headers.includes(h));
  if (missingHeaders.length > 0) {
    errors.push(`Missing required headers: ${missingHeaders.join(', ')}`);
  }

  // Parse data rows
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    try {
      const values = parseCSVLine(line);
      
      if (values.length !== headers.length) {
        errors.push(`Row ${i + 1}: Expected ${headers.length} columns, got ${values.length}`);
        continue;
      }

      const nodeData: any = {};
      headers.forEach((header, index) => {
        nodeData[header] = values[index] || '';
      });

      // Set graph name from first node
      if (!graphName && nodeData.GraphName) {
        graphName = nodeData.GraphName;
      }

      // Validate required fields
      if (!nodeData.Node) {
        errors.push(`Row ${i + 1}: Node name is required`);
        continue;
      }

      if (!nodeData.AgentType) {
        errors.push(`Row ${i + 1}: AgentType is required for node '${nodeData.Node}'`);
        continue;
      }

      const node: ParsedNode = {
        name: nodeData.Node,
        graphName: nodeData.GraphName || '',
        context: nodeData.Context || '',
        agentType: nodeData.AgentType,
        successNext: nodeData.Success_Next || '',
        failureNext: nodeData.Failure_Next || '',
        inputFields: nodeData.Input_Fields || '',
        outputField: nodeData.Output_Field || '',
        prompt: nodeData.Prompt || '',
        description: nodeData.Description || ''
      };

      nodes.push(node);

      // Add connections
      if (node.successNext) {
        node.successNext.split('|').forEach(nextNode => {
          const trimmedNext = nextNode.trim();
          if (trimmedNext) {
            connections.push({
              from: node.name,
              to: trimmedNext,
              type: 'success'
            });
          }
        });
      }

      if (node.failureNext) {
        node.failureNext.split('|').forEach(nextNode => {
          const trimmedNext = nextNode.trim();
          if (trimmedNext) {
            connections.push({
              from: node.name,
              to: trimmedNext,
              type: 'failure'
            });
          }
        });
      }

    } catch (parseError) {
      errors.push(`Row ${i + 1}: ${parseError.message}`);
    }
  }

  // Validate connections reference existing nodes
  const nodeNames = nodes.map(n => n.name);
  connections.forEach(conn => {
    if (!nodeNames.includes(conn.to)) {
      errors.push(`Connection references non-existent node: '${conn.to}'`);
    }
  });

  return { nodes, connections, graphName, errors };
}

// Helper function to parse a CSV line handling quotes and commas
function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  let i = 0;

  while (i < line.length) {
    const char = line[i];
    
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        // Escaped quote
        current += '"';
        i += 2;
      } else {
        // Toggle quote state
        inQuotes = !inQuotes;
        i++;
      }
    } else if (char === ',' && !inQuotes) {
      // End of field
      result.push(current.trim());
      current = '';
      i++;
    } else {
      current += char;
      i++;
    }
  }

  // Add the last field
  result.push(current.trim());
  
  return result;
}

// Helper function to generate Mermaid diagram
function generateMermaidDiagram(workflow: ParsedWorkflow): string {
  if (workflow.nodes.length === 0) {
    return '';
  }

  const lines: string[] = ['graph LR'];

  // Add nodes with styling
  workflow.nodes.forEach(node => {
    const nodeId = sanitizeNodeId(node.name);
    const agentType = getAgentTypeKey(node.agentType);
    const color = AGENT_TYPE_COLORS[agentType] || AGENT_TYPE_COLORS.unknown;
    
    // Create node with description
    const label = node.description || node.name;
    lines.push(`    ${nodeId}["${label}"]`);
    
    // Add styling
    lines.push(`    style ${nodeId} fill:${color},stroke:#333,stroke-width:2px,color:#fff`);
  });

  // Add connections
  workflow.connections.forEach(conn => {
    const fromId = sanitizeNodeId(conn.from);
    const toId = sanitizeNodeId(conn.to);
    
    if (conn.type === 'success') {
      lines.push(`    ${fromId} --> ${toId}`);
    } else {
      lines.push(`    ${fromId} -.-> ${toId}`);
    }
  });

  return lines.join('\n');
}

// Helper function to sanitize node IDs for Mermaid
function sanitizeNodeId(name: string): string {
  return name.replace(/[^a-zA-Z0-9]/g, '_');
}

// Helper function to get agent type key
function getAgentTypeKey(agentType: string): string {
  // Handle custom agents
  if (agentType.startsWith('custom:')) {
    return 'custom';
  }
  
  // Check if agent type exists in our color mapping
  if (agentType in AGENT_TYPE_COLORS) {
    return agentType;
  }
  
  return 'unknown';
}
