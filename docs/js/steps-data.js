/**
 * Data for the workflow steps.
 * Each step contains title, description, details, code, and visual representation.
 */
const stepsData = [
    {
        title: "1. CSV Workflow Definition",
        description: "AgentMap begins with a CSV file that defines the workflow structure.",
        details: "The CSV file contains rows defining each node in the workflow graph, including agents, edges, prompts, and routing logic.",
        code: `GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
SimpleQA,GetInput,,User input,input,ProcessInput,,user_query,input,"Please enter your question:"
SimpleQA,ProcessInput,,Process with LLM,openai,GenerateResponse,HandleError,input,answer,""
SimpleQA,GenerateResponse,,Format response,echo,END,,answer,formatted_answer,"Your answer is: {answer}"
SimpleQA,HandleError,,Handle error,echo,END,,error,error_message,"Sorry, an error occurred: {error}"`,
        visual: `
            <div class="code-block">
                <table class="workflow-table">
                    <thead>
                        <tr>
                            <th>GraphName</th>
                            <th>Node</th>
                            <th>Edge</th>
                            <th>Context</th>
                            <th>AgentType</th>
                            <th>Success_Next</th>
                            <th>Failure_Next</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="highlight-node">GetInput</td>
                            <td></td>
                            <td>User input</td>
                            <td>input</td>
                            <td>ProcessInput</td>
                            <td></td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="highlight-node">ProcessInput</td>
                            <td></td>
                            <td>Process with LLM</td>
                            <td>openai</td>
                            <td>GenerateResponse</td>
                            <td>HandleError</td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="highlight-node">GenerateResponse</td>
                            <td></td>
                            <td>Format response</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
                        </tr>
                        <tr>
                            <td>SimpleQA</td>
                            <td class="highlight-node">HandleError</td>
                            <td></td>
                            <td>Handle error</td>
                            <td>echo</td>
                            <td>END</td>
                            <td></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `
    },
    // Keep the rest of the steps data as is
    // ...
];

/**
 * Documentation files available in the project
 */
const documentationFiles = [
    { path: 'README.md', title: 'Main README' },
    { path: 'README_usage_details.md', title: 'Usage Details' },
    { path: 'README_cloud_storage.md', title: 'Cloud Storage' }
];