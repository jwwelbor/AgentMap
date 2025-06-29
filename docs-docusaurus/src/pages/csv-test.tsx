import React from 'react';
import Layout from '@theme/Layout';
import CSVTable from '@site/src/components/CSVTable';

export default function CSVTest(): JSX.Element {
  const testCSV = `GraphName,Node,AgentType,Success_Next,Input_Fields,Output_Field
TestFlow,Start,input,Process,user_input,data
TestFlow,Process,default,End,data,result
TestFlow,End,echo,,,output`;

  return (
    <Layout title="CSV Table Test" description="Testing CSVTable component">
      <div style={{ padding: '2rem' }}>
        <h1>CSV Table Component Test</h1>
        
        <h2>Test 1: Simple CSV</h2>
        <CSVTable 
          csvContent={testCSV}
          title="Simple Test Workflow"
          filename="test_workflow"
        />
        
        <h2>Test 2: Empty CSV</h2>
        <CSVTable 
          csvContent=""
          title="Empty CSV Test"
          filename="empty"
        />
        
        <h2>If you can see formatted tables above, the component is working!</h2>
      </div>
    </Layout>
  );
}
