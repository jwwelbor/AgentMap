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
            <div class="border border-gray-300 rounded-md p-4 bg-gray-900">
                <div class="flex flex-col space-y-2">
                    <div class="flex text-xs font-bold">
                        <div class="w-24 border-r border-gray-600 p-1">GraphName</div>
                        <div class="w-24 border-r border-gray-600 p-1">Node</div>
                        <div class="w-24 border-r border-gray-600 p-1">Edge</div>
                        <div class="w-32 border-r border-gray-600 p-1">Context</div>
                        <div class="w-24 border-r border-gray-600 p-1">AgentType</div>
                        <div class="w-24 border-r border-gray-600 p-1">Success_Next</div>
                        <div class="w-24 border-r border-gray-600 p-1">Failure_Next</div>
                    </div>
                    <div class="flex text-xs">
                        <div class="w-24 border-r border-gray-600 p-1">SimpleQA</div>
                        <div class="w-24 border-r border-gray-600 p-1 font-medium text-cyan-300">GetInput</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                        <div class="w-32 border-r border-gray-600 p-1">User input</div>
                        <div class="w-24 border-r border-gray-600 p-1">input</div>
                        <div class="w-24 border-r border-gray-600 p-1">ProcessInput</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                    </div>
                    <div class="flex text-xs">
                        <div class="w-24 border-r border-gray-600 p-1">SimpleQA</div>
                        <div class="w-24 border-r border-gray-600 p-1 font-medium text-cyan-300">ProcessInput</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                        <div class="w-32 border-r border-gray-600 p-1">Process with LLM</div>
                        <div class="w-24 border-r border-gray-600 p-1">openai</div>
                        <div class="w-24 border-r border-gray-600 p-1">GenerateResponse</div>
                        <div class="w-24 border-r border-gray-600 p-1">HandleError</div>
                    </div>
                    <div class="flex text-xs">
                        <div class="w-24 border-r border-gray-600 p-1">SimpleQA</div>
                        <div class="w-24 border-r border-gray-600 p-1 font-medium text-cyan-300">GenerateResponse</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                        <div class="w-32 border-r border-gray-600 p-1">Format response</div>
                        <div class="w-24 border-r border-gray-600 p-1">echo</div>
                        <div class="w-24 border-r border-gray-600 p-1">END</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                    </div>
                    <div class="flex text-xs">
                        <div class="w-24 border-r border-gray-600 p-1">SimpleQA</div>
                        <div class="w-24 border-r border-gray-600 p-1 font-medium text-cyan-300">HandleError</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                        <div class="w-32 border-r border-gray-600 p-1">Handle error</div>
                        <div class="w-24 border-r border-gray-600 p-1">echo</div>
                        <div class="w-24 border-r border-gray-600 p-1">END</div>
                        <div class="w-24 border-r border-gray-600 p-1"></div>
                    </div>
                </div>
            </div>
        `
    },
    // Add the remaining step data objects here...
];

/**
 * Documentation files available in the project
 */
const documentationFiles = [
    { path: 'README.md', title: 'Main README' },
    { path: 'README_usage_details.md', title: 'Usage Details' },
    { path: 'README_cloud_storage.md', title: 'Cloud Storage' }
];