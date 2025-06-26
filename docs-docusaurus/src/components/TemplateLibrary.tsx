import React, { useState, useMemo } from 'react';
import styles from './TemplateLibrary.module.css';

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: 'Automation' | 'Data Processing' | 'AI/LLM' | 'Monitoring' | 'Integration' | 'Utility';
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  tags: string[];
  requiredAgents: string[];
  useCase: string;
  csvContent: string;
  outputExample?: string;
  configNotes?: string[];
}

const TEMPLATES: WorkflowTemplate[] = [
  {
    id: 'weather-notification',
    name: 'Weather Notification Bot',
    description: 'Daily weather alerts with intelligent notifications based on conditions',
    category: 'Automation',
    difficulty: 'Beginner',
    tags: ['notifications', 'weather', 'daily-automation'],
    requiredAgents: ['llm', 'echo'],
    useCase: 'Get daily weather updates with contextual advice (umbrella reminders, outfit suggestions)',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
WeatherBot,GetWeather,,Get current weather data,input,AnalyzeWeather,,location,weather_data,Enter your location (e.g. New York City):
WeatherBot,AnalyzeWeather,,"{'temperature': 0.7, 'model': 'gpt-3.5-turbo'}",llm,FormatNotification,ErrorHandler,weather_data,analysis,Analyze this weather data and provide practical advice: {weather_data}. Include temperature, conditions, and helpful recommendations for clothing or activities.
WeatherBot,FormatNotification,,Format the final notification,echo,End,,analysis,notification,
WeatherBot,End,,Weather notification complete,echo,,,notification,final_message,Weather update sent successfully!
WeatherBot,ErrorHandler,,Handle errors gracefully,echo,End,,error,error_message,Unable to get weather data. Please try again later.`,
    outputExample: "🌤️ NYC Weather Update: 72°F, partly cloudy. Perfect day for a walk! Light jacket recommended for evening.",
    configNotes: [
      "Replace 'input' agent with weather API integration for automation",
      "Add scheduling for daily notifications",
      "Customize prompt for regional preferences"
    ]
  },
  {
    id: 'daily-report-generator',
    name: 'Daily Report Generator',
    description: 'Automated data collection and report generation from multiple sources',
    category: 'Data Processing',
    difficulty: 'Intermediate',
    tags: ['reporting', 'automation', 'data-aggregation'],
    requiredAgents: ['csv_reader', 'llm', 'file_writer'],
    useCase: 'Generate daily business reports by collecting data from CSV files and creating formatted summaries',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DailyReport,LoadSalesData,,"{'format': 'records'}",csv_reader,LoadMetrics,ErrorHandler,collection,sales_data,data/daily_sales.csv
DailyReport,LoadMetrics,,"{'format': 'records'}",csv_reader,AnalyzeData,ErrorHandler,collection,metrics_data,data/metrics.csv
DailyReport,AnalyzeData,,"{'temperature': 0.3, 'model': 'gpt-4'}",llm,GenerateReport,ErrorHandler,sales_data|metrics_data,analysis,Create a comprehensive daily business report from this data: Sales: {sales_data} Metrics: {metrics_data}. Include key insights, trends, and actionable recommendations.
DailyReport,GenerateReport,,"{'mode': 'write'}",file_writer,FormatSummary,ErrorHandler,analysis,report_result,reports/daily_report.md
DailyReport,FormatSummary,,Create executive summary,llm,SaveSummary,ErrorHandler,analysis,summary,Create a 3-bullet executive summary of this report: {analysis}
DailyReport,SaveSummary,,"{'mode': 'write'}",file_writer,End,ErrorHandler,summary,summary_result,reports/executive_summary.txt
DailyReport,End,,Report generation complete,echo,,,summary_result,final_message,Daily report generated successfully!
DailyReport,ErrorHandler,,Handle processing errors,echo,End,,error,error_message,Report generation failed: {error}`,
    outputExample: "✅ Daily report saved to reports/daily_report.md with executive summary",
    configNotes: [
      "Ensure CSV files exist in data/ directory",
      "Customize report template in LLM prompts",
      "Add email integration for automatic distribution"
    ]
  },
  {
    id: 'customer-feedback-analyzer',
    name: 'Customer Feedback Analyzer',
    description: 'Sentiment analysis and categorization of customer feedback',
    category: 'AI/LLM',
    difficulty: 'Intermediate',
    tags: ['sentiment-analysis', 'customer-service', 'nlp'],
    requiredAgents: ['csv_reader', 'llm', 'csv_writer'],
    useCase: 'Analyze customer feedback for sentiment, extract key themes, and categorize issues',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
FeedbackAnalyzer,LoadFeedback,,"{'format': 'records'}",csv_reader,AnalyzeSentiment,ErrorHandler,collection,feedback_data,data/customer_feedback.csv
FeedbackAnalyzer,AnalyzeSentiment,,"{'temperature': 0.2, 'model': 'gpt-4'}",llm,CategorizeIssues,ErrorHandler,feedback_data,sentiment_analysis,Analyze the sentiment of this customer feedback and rate each on a scale of 1-5 (5=very positive, 1=very negative). Return structured data: {feedback_data}
FeedbackAnalyzer,CategorizeIssues,,"{'temperature': 0.3}",llm,ExtractThemes,ErrorHandler,feedback_data|sentiment_analysis,categories,Categorize these customer issues into main themes (e.g., Product Quality, Customer Service, Shipping, etc.): {feedback_data}. Sentiment context: {sentiment_analysis}
FeedbackAnalyzer,ExtractThemes,,Extract key themes and insights,llm,CompileResults,ErrorHandler,feedback_data|sentiment_analysis|categories,themes,Extract the top 3 themes and actionable insights from this feedback analysis: Feedback: {feedback_data}, Sentiment: {sentiment_analysis}, Categories: {categories}
FeedbackAnalyzer,CompileResults,,Compile final analysis,llm,SaveResults,ErrorHandler,sentiment_analysis|categories|themes,final_analysis,Create a comprehensive customer feedback report with: 1) Sentiment summary 2) Issue categories 3) Key themes 4) Recommended actions. Data: Sentiment: {sentiment_analysis}, Categories: {categories}, Themes: {themes}
FeedbackAnalyzer,SaveResults,,"{'format': 'records', 'mode': 'write'}",csv_writer,End,ErrorHandler,final_analysis,save_result,analysis/feedback_analysis.csv
FeedbackAnalyzer,End,,Analysis complete,echo,,,save_result,final_message,Customer feedback analysis saved successfully!
FeedbackAnalyzer,ErrorHandler,,Handle analysis errors,echo,End,,error,error_message,Feedback analysis failed: {error}`,
    outputExample: "📊 Analyzed 150 feedback entries: 68% positive, main themes: shipping delays, product quality",
    configNotes: [
      "Ensure feedback CSV has 'feedback' and 'customer_id' columns",
      "Adjust sentiment scale in prompts as needed",
      "Add integration with CRM systems for follow-up actions"
    ]
  },
  {
    id: 'social-media-monitor',
    name: 'Social Media Monitor',
    description: 'Monitor and analyze social media mentions with alert system',
    category: 'Monitoring',
    difficulty: 'Advanced',
    tags: ['social-media', 'monitoring', 'alerts', 'sentiment'],
    requiredAgents: ['json_reader', 'llm', 'branching', 'echo'],
    useCase: 'Monitor social media mentions, analyze sentiment, and trigger alerts for negative feedback',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
SocialMonitor,LoadMentions,,"{'format': 'list'}",json_reader,AnalyzeMentions,ErrorHandler,collection,mentions_data,data/social_mentions.json
SocialMonitor,AnalyzeMentions,,"{'temperature': 0.2, 'model': 'gpt-4'}",llm,CheckSentiment,ErrorHandler,mentions_data,analysis,Analyze these social media mentions for sentiment, urgency, and influence level. Return JSON with sentiment_score (1-10), urgency (low/medium/high), and influence_score (1-10): {mentions_data}
SocialMonitor,CheckSentiment,,Check if immediate action needed,branching,TriggerAlert,GenerateReport,analysis,routing_decision,
SocialMonitor,TriggerAlert,,Send immediate alert for negative mentions,echo,GenerateReport,,analysis,alert_sent,🚨 URGENT: Negative social mention detected requiring immediate attention!
SocialMonitor,GenerateReport,,"{'temperature': 0.3}",llm,SaveReport,ErrorHandler,mentions_data|analysis,report,Generate a social media monitoring report including: 1) Mention summary 2) Sentiment trends 3) High-influence accounts 4) Recommended responses. Data: {mentions_data}. Analysis: {analysis}
SocialMonitor,SaveReport,,"{'mode': 'write'}",file_writer,End,ErrorHandler,report,save_result,reports/social_media_report.md
SocialMonitor,End,,Monitoring cycle complete,echo,,,save_result,final_message,Social media monitoring complete. Report saved.
SocialMonitor,ErrorHandler,,Handle monitoring errors,echo,End,,error,error_message,Social media monitoring failed: {error}`,
    outputExample: "📱 Monitored 25 mentions: 3 high-priority alerts, 1 urgent response needed",
    configNotes: [
      "Configure branching logic: negative sentiment (score < 4) AND high influence (> 7) triggers alerts",
      "Integrate with social media APIs for real-time data",
      "Set up webhook notifications for urgent alerts"
    ]
  },
  {
    id: 'data-etl-pipeline',
    name: 'Data ETL Pipeline',
    description: 'Extract, transform, and load data between different formats and systems',
    category: 'Data Processing',
    difficulty: 'Advanced',
    tags: ['etl', 'data-transformation', 'csv', 'json'],
    requiredAgents: ['csv_reader', 'llm', 'json_writer', 'csv_writer'],
    useCase: 'Transform data from CSV to JSON format with validation and enrichment',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DataETL,ExtractData,,"{'format': 'records'}",csv_reader,ValidateData,ErrorHandler,collection,raw_data,data/source_data.csv
DataETL,ValidateData,,"{'temperature': 0.1, 'model': 'gpt-3.5-turbo'}",llm,TransformData,ErrorHandler,raw_data,validation_result,Validate this data for completeness and format. Flag any missing required fields or invalid formats: {raw_data}. Return validation status and list of issues.
DataETL,TransformData,,"{'temperature': 0.2}",llm,EnrichData,ErrorHandler,raw_data|validation_result,transformed_data,Transform this CSV data to JSON format with standardized field names. Apply data cleaning and normalization: {raw_data}. Validation context: {validation_result}
DataETL,EnrichData,,Add calculated fields and metadata,llm,SaveJSON,ErrorHandler,transformed_data,enriched_data,Enrich this data by adding calculated fields, categories, and metadata: {transformed_data}. Add processing timestamp and data quality score.
DataETL,SaveJSON,,"{'format': 'dict', 'indent': 2}",json_writer,CreateSummary,ErrorHandler,enriched_data,json_result,data/output/transformed_data.json
DataETL,CreateSummary,,Generate processing summary,llm,SaveSummary,ErrorHandler,validation_result|json_result,summary,Create an ETL processing summary including: records processed, validation results, transformations applied, and data quality metrics. Validation: {validation_result}, Result: {json_result}
DataETL,SaveSummary,,"{'format': 'records', 'mode': 'write'}",csv_writer,End,ErrorHandler,summary,summary_result,data/output/etl_summary.csv
DataETL,End,,ETL pipeline complete,echo,,,summary_result,final_message,Data ETL pipeline completed successfully!
DataETL,ErrorHandler,,Handle ETL errors,echo,End,,error,error_message,ETL pipeline failed: {error}`,
    outputExample: "🔄 ETL Complete: 1,250 records transformed, 98.5% data quality score",
    configNotes: [
      "Customize field mappings in transform prompts",
      "Add data validation rules specific to your use case",
      "Configure output directory structure"
    ]
  },
  {
    id: 'document-summarizer',
    name: 'Document Summarizer',
    description: 'Intelligent document processing and multi-level summarization',
    category: 'AI/LLM',
    difficulty: 'Intermediate',
    tags: ['document-processing', 'summarization', 'ai'],
    requiredAgents: ['file_reader', 'llm', 'file_writer'],
    useCase: 'Process documents to create executive summaries, key points, and action items',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
DocSummarizer,LoadDocument,,"{'chunk_size': 2000, 'should_split': true}",file_reader,CreateSummary,ErrorHandler,collection,document_content,
DocSummarizer,CreateSummary,,"{'temperature': 0.3, 'model': 'gpt-4'}",llm,ExtractKeyPoints,ErrorHandler,document_content,summary,Create a comprehensive summary of this document. Focus on main themes, key findings, and important conclusions: {document_content}
DocSummarizer,ExtractKeyPoints,,Extract actionable insights,llm,CreateExecutiveSummary,ErrorHandler,document_content|summary,key_points,Extract the 5 most important key points and any action items from this document: {document_content}. Context: {summary}
DocSummarizer,CreateExecutiveSummary,,Create executive-level summary,llm,SaveSummary,ErrorHandler,summary|key_points,executive_summary,Create a concise executive summary (2-3 paragraphs) suitable for leadership review: Summary: {summary}, Key Points: {key_points}
DocSummarizer,SaveSummary,,"{'mode': 'write'}",file_writer,SaveKeyPoints,ErrorHandler,executive_summary,summary_result,output/executive_summary.md
DocSummarizer,SaveKeyPoints,,"{'mode': 'write'}",file_writer,SaveFullAnalysis,ErrorHandler,key_points,keypoints_result,output/key_points.md
DocSummarizer,SaveFullAnalysis,,"{'mode': 'write'}",file_writer,End,ErrorHandler,summary,analysis_result,output/full_analysis.md
DocSummarizer,End,,Document processing complete,echo,,,analysis_result,final_message,Document summarization completed successfully!
DocSummarizer,ErrorHandler,,Handle processing errors,echo,End,,error,error_message,Document processing failed: {error}`,
    outputExample: "📄 Document processed: 15-page report summarized into 3 key deliverables",
    configNotes: [
      "Supports PDF, TXT, MD file formats",
      "Adjust chunk_size based on document length",
      "Customize summary style in prompts"
    ]
  },
  {
    id: 'api-health-checker',
    name: 'API Health Checker',
    description: 'Monitor API endpoints and generate health reports with alerting',
    category: 'Monitoring',
    difficulty: 'Intermediate',
    tags: ['api-monitoring', 'health-check', 'alerts'],
    requiredAgents: ['json_reader', 'llm', 'branching', 'file_writer'],
    useCase: 'Check API endpoint health, analyze response times, and alert on issues',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
APIHealthCheck,LoadEndpoints,,"{'format': 'list'}",json_reader,AnalyzeHealth,ErrorHandler,collection,endpoints_data,config/api_endpoints.json
APIHealthCheck,AnalyzeHealth,,"{'temperature': 0.1, 'model': 'gpt-3.5-turbo'}",llm,CheckStatus,ErrorHandler,endpoints_data,health_analysis,Analyze this API health data and determine status for each endpoint. Look for response times >500ms, error rates >1%, and downtime. Return structured status: {endpoints_data}
APIHealthCheck,CheckStatus,,Determine if alerts needed,branching,TriggerAlert,GenerateReport,health_analysis,alert_decision,
APIHealthCheck,TriggerAlert,,Send critical alerts,echo,GenerateReport,,health_analysis,alert_sent,🚨 API ALERT: Critical endpoints detected requiring immediate attention!
APIHealthCheck,GenerateReport,,"{'temperature': 0.2}",llm,SaveReport,ErrorHandler,endpoints_data|health_analysis,health_report,Generate a comprehensive API health report including: 1) Endpoint status summary 2) Performance metrics 3) Error analysis 4) Recommendations. Data: {endpoints_data}. Analysis: {health_analysis}
APIHealthCheck,SaveReport,,"{'mode': 'write'}",file_writer,CreateDashboard,ErrorHandler,health_report,report_result,reports/api_health_report.md
APIHealthCheck,CreateDashboard,,Create monitoring dashboard data,llm,SaveDashboard,ErrorHandler,health_analysis,dashboard_data,Create dashboard-ready JSON data from this health analysis for visualization: {health_analysis}
APIHealthCheck,SaveDashboard,,"{'mode': 'write'}",file_writer,End,ErrorHandler,dashboard_data,dashboard_result,monitoring/dashboard_data.json
APIHealthCheck,End,,Health check complete,echo,,,dashboard_result,final_message,API health check completed. Reports generated.
APIHealthCheck,ErrorHandler,,Handle monitoring errors,echo,End,,error,error_message,API health check failed: {error}`,
    outputExample: "🔍 Health Check: 12/15 APIs healthy, 2 warnings, 1 critical alert triggered",
    configNotes: [
      "Configure endpoint list in config/api_endpoints.json",
      "Set alert thresholds in branching logic",
      "Integrate with monitoring tools like Grafana"
    ]
  },
  {
    id: 'email-classifier',
    name: 'Email Classifier',
    description: 'Intelligent email categorization and priority routing system',
    category: 'AI/LLM',
    difficulty: 'Beginner',
    tags: ['email-processing', 'classification', 'automation'],
    requiredAgents: ['csv_reader', 'llm', 'branching', 'csv_writer'],
    useCase: 'Automatically categorize and prioritize incoming emails based on content and sender',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
EmailClassifier,LoadEmails,,"{'format': 'records'}",csv_reader,ClassifyEmails,ErrorHandler,collection,email_data,data/incoming_emails.csv
EmailClassifier,ClassifyEmails,,"{'temperature': 0.2, 'model': 'gpt-3.5-turbo'}",llm,DeterminePriority,ErrorHandler,email_data,classification,Classify these emails into categories: Support, Sales, Marketing, Technical, Urgent. Also determine sentiment (positive/neutral/negative): {email_data}
EmailClassifier,DeterminePriority,,Assess priority level,llm,RouteEmails,ErrorHandler,email_data|classification,priority_assessment,Determine priority level (High/Medium/Low) for each email based on content urgency, sender importance, and keywords: {email_data}. Classification context: {classification}
EmailClassifier,RouteEmails,,Route based on classification,branching,ProcessUrgent,ProcessNormal,priority_assessment,routing_decision,
EmailClassifier,ProcessUrgent,,Handle urgent emails,echo,SaveResults,,priority_assessment,urgent_processed,⚡ Urgent emails flagged for immediate attention
EmailClassifier,ProcessNormal,,Handle normal priority emails,echo,SaveResults,,priority_assessment,normal_processed,📧 Standard emails categorized and queued
EmailClassifier,SaveResults,,"{'format': 'records', 'mode': 'write'}",csv_writer,GenerateSummary,ErrorHandler,classification|priority_assessment,save_result,data/classified_emails.csv
EmailClassifier,GenerateSummary,,Create processing summary,llm,End,ErrorHandler,classification|priority_assessment,summary,Create an email processing summary with category counts and priority distribution: Classifications: {classification}, Priorities: {priority_assessment}
EmailClassifier,End,,Email classification complete,echo,,,summary,final_message,Email classification completed successfully!
EmailClassifier,ErrorHandler,,Handle classification errors,echo,End,,error,error_message,Email classification failed: {error}`,
    outputExample: "📧 Processed 45 emails: 3 urgent, 15 support tickets, 12 sales inquiries",
    configNotes: [
      "Ensure email CSV has 'subject', 'sender', 'content' columns",
      "Configure urgency keywords for branching logic",
      "Add integration with email systems for automation"
    ]
  },
  {
    id: 'translation-workflow',
    name: 'Translation Workflow',
    description: 'Multi-language document translation with quality assurance',
    category: 'AI/LLM',
    difficulty: 'Intermediate',
    tags: ['translation', 'multilingual', 'qa'],
    requiredAgents: ['file_reader', 'llm', 'file_writer'],
    useCase: 'Translate documents between languages with quality checks and formatting preservation',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
TranslationWorkflow,LoadDocument,,"{'chunk_size': 1500, 'should_split': true}",file_reader,DetectLanguage,ErrorHandler,collection,source_content,
TranslationWorkflow,DetectLanguage,,"{'temperature': 0.1}",llm,TranslateContent,ErrorHandler,source_content,language_info,Detect the source language of this text and confirm the target language for translation: {source_content}. Respond with source_language and confidence_level.
TranslationWorkflow,TranslateContent,,"{'temperature': 0.3, 'model': 'gpt-4'}",llm,QualityCheck,ErrorHandler,source_content|language_info,translation,Translate this text from the detected source language to the target language. Preserve formatting, maintain professional tone, and ensure cultural appropriateness: {source_content}. Language context: {language_info}
TranslationWorkflow,QualityCheck,,Review translation quality,llm,FormatOutput,ErrorHandler,source_content|translation,quality_review,Review this translation for accuracy, fluency, and completeness. Rate quality (1-10) and note any issues: Original: {source_content}. Translation: {translation}
TranslationWorkflow,FormatOutput,,Format final translation,llm,SaveTranslation,ErrorHandler,translation|quality_review,formatted_translation,Format the final translation with proper structure and any necessary corrections: {translation}. Quality notes: {quality_review}
TranslationWorkflow,SaveTranslation,,"{'mode': 'write'}",file_writer,SaveQualityReport,ErrorHandler,formatted_translation,translation_result,output/translated_document.txt
TranslationWorkflow,SaveQualityReport,,"{'mode': 'write'}",file_writer,End,ErrorHandler,quality_review,quality_result,output/translation_quality_report.txt
TranslationWorkflow,End,,Translation workflow complete,echo,,,quality_result,final_message,Document translation completed with quality report!
TranslationWorkflow,ErrorHandler,,Handle translation errors,echo,End,,error,error_message,Translation workflow failed: {error}`,
    outputExample: "🌐 Translation complete: EN→ES, Quality score: 9.2/10, 3 pages processed",
    configNotes: [
      "Specify target language in initial input",
      "Adjust chunk_size for optimal translation context",
      "Add glossary terms for domain-specific translation"
    ]
  },
  {
    id: 'content-moderator',
    name: 'Content Moderator',
    description: 'AI-powered content moderation with policy compliance checking',
    category: 'AI/LLM',
    difficulty: 'Advanced',
    tags: ['content-moderation', 'safety', 'compliance'],
    requiredAgents: ['csv_reader', 'llm', 'branching', 'csv_writer'],
    useCase: 'Moderate user-generated content for safety, policy compliance, and quality standards',
    csvContent: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ContentModerator,LoadContent,,"{'format': 'records'}",csv_reader,InitialScreen,ErrorHandler,collection,content_data,data/user_content.csv
ContentModerator,InitialScreen,,"{'temperature': 0.1, 'model': 'gpt-4'}",llm,DeepAnalysis,ErrorHandler,content_data,initial_screening,Screen this content for obvious policy violations, inappropriate language, and spam. Rate safety level (1-10, 10=completely safe): {content_data}
ContentModerator,DeepAnalysis,,Detailed content analysis,llm,PolicyCheck,ErrorHandler,content_data|initial_screening,detailed_analysis,Perform detailed analysis of this content for: 1) Hate speech 2) Violence 3) Sexual content 4) Harassment 5) Misinformation. Content: {content_data}. Initial screening: {initial_screening}
ContentModerator,PolicyCheck,,Check against content policies,llm,DetermineAction,ErrorHandler,content_data|detailed_analysis,policy_compliance,Check this content against platform policies and community guidelines. Determine if content should be: approved, flagged for review, or removed. Analysis: {detailed_analysis}
ContentModerator,DetermineAction,,Decide on moderation action,branching,FlagContent,ApproveContent,policy_compliance,moderation_decision,
ContentModerator,FlagContent,,Flag problematic content,echo,SaveResults,,policy_compliance,flagged_result,🚩 Content flagged for manual review or removal
ContentModerator,ApproveContent,,Approve safe content,echo,SaveResults,,policy_compliance,approved_result,✅ Content approved for publication
ContentModerator,SaveResults,,"{'format': 'records', 'mode': 'write'}",csv_writer,GenerateReport,ErrorHandler,initial_screening|detailed_analysis|policy_compliance,save_result,data/moderation_results.csv
ContentModerator,GenerateReport,,Create moderation summary,llm,End,ErrorHandler,initial_screening|detailed_analysis|policy_compliance,moderation_report,Generate a content moderation report with statistics, flagged items, and trend analysis: Screening: {initial_screening}, Analysis: {detailed_analysis}, Compliance: {policy_compliance}
ContentModerator,End,,Content moderation complete,echo,,,moderation_report,final_message,Content moderation completed successfully!
ContentModerator,ErrorHandler,,Handle moderation errors,echo,End,,error,error_message,Content moderation failed: {error}`,
    outputExample: "🛡️ Moderated 200 posts: 185 approved, 12 flagged for review, 3 removed",
    configNotes: [
      "Configure policy rules in branching conditions",
      "Adjust safety thresholds based on platform needs",
      "Add human review queue for borderline cases"
    ]
  }
];

const CATEGORY_COLORS = {
  'Automation': '#4CAF50',      // Green
  'Data Processing': '#FF9800', // Orange
  'AI/LLM': '#2196F3',         // Blue
  'Monitoring': '#E91E63',     // Pink
  'Integration': '#9C27B0',    // Purple
  'Utility': '#607D8B'         // Blue Grey
};

const CATEGORY_ICONS = {
  'Automation': '🤖',
  'Data Processing': '📊',
  'AI/LLM': '🧠',
  'Monitoring': '👁️',
  'Integration': '🔗',
  'Utility': '🛠️'
};

const DIFFICULTY_COLORS = {
  'Beginner': '#4CAF50',    // Green
  'Intermediate': '#FF9800', // Orange
  'Advanced': '#F44336'     // Red
};

const DIFFICULTY_ICONS = {
  'Beginner': '🟢',
  'Intermediate': '🟡',
  'Advanced': '🔴'
};

export default function TemplateLibrary(): JSX.Element {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('All');
  const [copiedTemplate, setCopiedTemplate] = useState<string | null>(null);

  const categories = ['All', ...Object.keys(CATEGORY_COLORS)];
  const difficulties = ['All', 'Beginner', 'Intermediate', 'Advanced'];

  const filteredTemplates = useMemo(() => {
    return TEMPLATES.filter(template => {
      const matchesSearch = 
        template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.useCase.toLowerCase().includes(searchTerm.toLowerCase()) ||
        template.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesCategory = 
        selectedCategory === 'All' || template.category === selectedCategory;
      
      const matchesDifficulty = 
        selectedDifficulty === 'All' || template.difficulty === selectedDifficulty;
      
      return matchesSearch && matchesCategory && matchesDifficulty;
    });
  }, [searchTerm, selectedCategory, selectedDifficulty]);

  const copyToClipboard = async (text: string, templateId: string) => {
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
        try {
          document.execCommand('copy');
        } catch (fallbackErr) {
          console.error('Fallback copy failed: ', fallbackErr);
        }
        document.body.removeChild(textArea);
      }
      setCopiedTemplate(templateId);
      setTimeout(() => setCopiedTemplate(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      setCopiedTemplate(templateId);
      setTimeout(() => setCopiedTemplate(null), 1000);
    }
  };

  const openInPlayground = (csvContent: string) => {
    // This would integrate with the actual playground - for now just copy
    copyToClipboard(csvContent, 'playground');
    // In a real implementation, this would navigate to playground with the content pre-loaded
    console.log('Opening in playground...', csvContent);
  };

  return (
    <div className={styles.templateLibrary}>
      <div className={styles.header}>
        <h1>AgentMap Template Library</h1>
        <p>Ready-to-use workflow templates to get you started quickly</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.searchContainer}>
          <input
            type="text"
            placeholder="Search templates by name, description, or tags..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.filters}>
          <div className={styles.filterGroup}>
            <label>Category:</label>
            <div className={styles.categoryFilters}>
              {categories.map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`${styles.filterButton} ${
                    selectedCategory === category ? styles.active : ''
                  }`}
                  style={{
                    backgroundColor: selectedCategory === category 
                      ? (category !== 'All' ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] : '#333')
                      : 'transparent',
                    borderColor: category !== 'All' 
                      ? CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] 
                      : '#333'
                  }}
                >
                  {category !== 'All' && CATEGORY_ICONS[category as keyof typeof CATEGORY_ICONS]} {category}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.filterGroup}>
            <label>Difficulty:</label>
            <div className={styles.difficultyFilters}>
              {difficulties.map(difficulty => (
                <button
                  key={difficulty}
                  onClick={() => setSelectedDifficulty(difficulty)}
                  className={`${styles.filterButton} ${
                    selectedDifficulty === difficulty ? styles.active : ''
                  }`}
                  style={{
                    backgroundColor: selectedDifficulty === difficulty 
                      ? (difficulty !== 'All' ? DIFFICULTY_COLORS[difficulty as keyof typeof DIFFICULTY_COLORS] : '#333')
                      : 'transparent',
                    borderColor: difficulty !== 'All' 
                      ? DIFFICULTY_COLORS[difficulty as keyof typeof DIFFICULTY_COLORS] 
                      : '#333'
                  }}
                >
                  {difficulty !== 'All' && DIFFICULTY_ICONS[difficulty as keyof typeof DIFFICULTY_ICONS]} {difficulty}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className={styles.templateGrid}>
        {filteredTemplates.map((template) => (
          <div key={template.id} className={styles.templateCard}>
            <div className={styles.cardHeader}>
              <div 
                className={styles.categoryBadge}
                style={{ backgroundColor: CATEGORY_COLORS[template.category] }}
              >
                {CATEGORY_ICONS[template.category]} {template.category}
              </div>
              <div 
                className={styles.difficultyBadge}
                style={{ backgroundColor: DIFFICULTY_COLORS[template.difficulty] }}
              >
                {DIFFICULTY_ICONS[template.difficulty]} {template.difficulty}
              </div>
            </div>

            <div className={styles.templateInfo}>
              <h3>{template.name}</h3>
              <p className={styles.description}>{template.description}</p>
              
              <div className={styles.useCase}>
                <strong>Use Case:</strong> {template.useCase}
              </div>

              <div className={styles.tags}>
                {template.tags.map(tag => (
                  <span key={tag} className={styles.tag}>{tag}</span>
                ))}
              </div>

              <div className={styles.requirements}>
                <strong>Required Agents:</strong>
                <div className={styles.agentList}>
                  {template.requiredAgents.map(agent => (
                    <code key={agent} className={styles.agentType}>{agent}</code>
                  ))}
                </div>
              </div>

              {template.outputExample && (
                <div className={styles.example}>
                  <strong>Example Output:</strong>
                  <div className={styles.exampleOutput}>{template.outputExample}</div>
                </div>
              )}

              {template.configNotes && template.configNotes.length > 0 && (
                <div className={styles.configNotes}>
                  <strong>Configuration Notes:</strong>
                  <ul>
                    {template.configNotes.map((note, index) => (
                      <li key={index}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className={styles.actions}>
              <button
                onClick={() => copyToClipboard(template.csvContent, template.id)}
                className={styles.copyButton}
              >
                {copiedTemplate === template.id ? '✓ Copied!' : '📋 Copy CSV'}
              </button>
              <button
                onClick={() => openInPlayground(template.csvContent)}
                className={styles.playgroundButton}
              >
                🚀 Open in Playground
              </button>
            </div>

            <details className={styles.csvPreview}>
              <summary>View CSV Content</summary>
              <pre className={styles.csvCode}>{template.csvContent}</pre>
            </details>
          </div>
        ))}
      </div>

      {filteredTemplates.length === 0 && (
        <div className={styles.noResults}>
          <p>No templates found matching your criteria.</p>
          <p>Try adjusting your search term or filters.</p>
        </div>
      )}

      <div className={styles.footer}>
        <p>
          Found {filteredTemplates.length} of {TEMPLATES.length} templates. 
          Need help customizing a template? Check out the{' '}
          <a href="/docs/guides/template-customization">template customization guide</a> or{' '}
          <a href="/docs/getting-started/quick-start">quick start tutorial</a>.
        </p>
      </div>
    </div>
  );
}
