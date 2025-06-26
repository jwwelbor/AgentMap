import clsx from 'clsx';
import Heading from '@theme/Heading';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

// What Can I Build Section
function WhatCanIBuild() {
  const examples = [
    {
      title: '🌐 API-Driven Bots',
      description: 'API driven bots (e.g. WeatherBot, FlightBot, StatusBot) - connect to any API with AI processing',
      link: '/docs/tutorials/weather-bot'
    },
    {
      title: '📊 Data Pipeline',
      description: 'Transform and analyze data from multiple sources automatically',
      link: '/docs/tutorials/data-processing-pipeline'
    },
    {
      title: '📧 Customer Support Bot',
      description: 'Smart email categorization and automated responses',
      link: '/docs/tutorials/customer-support-bot'
    },
    {
      title: '🔍 Document Analyzer',
      description: 'AI-powered document processing and analysis',
      link: '/docs/tutorials/document-analyzer'
    },
    {
      title: '🔗 API Integrations',
      description: 'Connect to external services and APIs seamlessly',
      link: '/docs/tutorials/api-integration'
    },
    {
      title: '💼 Business Automator',
      description: 'Streamline invoicing, reporting, and customer communication',
      link: '/docs/guides/understanding-workflows'
    }
  ];

  return (
    <section className={styles.whatSection} id="what-can-i-build">
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2" className={styles.sectionTitle}>
            What Can I Build?
          </Heading>
          <p className={styles.sectionSubtitle}>
            Real workflows that solve real problems - all defined in simple CSV files
          </p>
        </div>
        <div className={styles.examplesGrid}>
          {examples.map((example, idx) => (
            <Link key={idx} to={example.link} className={styles.exampleCard}>
              <h4 className={styles.exampleTitle}>{example.title}</h4>
              <p className={styles.exampleDescription}>{example.description}</p>
              <div className={styles.exampleCta}>View Tutorial →</div>
            </Link>
          ))}
        </div>
        <div className={styles.sectionCta}>
          <Link to="/docs/intro" className="button button--primary button--lg">
            See Full Tutorial
          </Link>
        </div>
      </div>
    </section>
  );
}

// How It Works Section
function HowItWorks() {
  const steps = [
    {
      number: '1',
      title: 'Define Your Workflow',
      description: 'Create a simple CSV file describing what you want your AI agents to do',
      icon: '📝'
    },
    {
      number: '2',
      title: 'Configure Agents',
      description: 'Set up your AI agents with roles, permissions, and data sources',
      icon: '🤖'
    },
    {
      number: '3',
      title: 'Deploy & Monitor',
      description: 'Launch your workflow and watch it work automatically',
      icon: '🚀'
    }
  ];

  return (
    <section className={styles.howSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2" className={styles.sectionTitle}>
            How It Works
          </Heading>
          <p className={styles.sectionSubtitle}>
            Three simple steps to production AI workflows
          </p>
        </div>
        <div className={styles.stepsContainer}>
          {steps.map((step, idx) => (
            <div key={idx} className={styles.stepCard}>
              <div className={styles.stepIcon}>{step.icon}</div>
              <div className={styles.stepNumber}>{step.number}</div>
              <h3 className={styles.stepTitle}>{step.title}</h3>
              <p className={styles.stepDescription}>{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// Why AgentMap Section
function WhyAgentMap() {
  const benefits = [
    {
      title: 'No Code Required',
      description: 'Build powerful AI workflows using familiar CSV files - no programming experience needed.',
      icon: '✨'
    },
    {
      title: 'Production Ready',
      description: 'Scale from prototype to production with enterprise-grade reliability and monitoring.',
      icon: '🛡️'
    },
    {
      title: 'Open Source',
      description: 'Join a vibrant community of builders. Extend, customize, and contribute to the platform.',
      icon: '🌟'
    }
  ];

  return (
    <section className={styles.whySection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2" className={styles.sectionTitle}>
            Why AgentMap?
          </Heading>
          <p className={styles.sectionSubtitle}>
            The simplest way to build AI workflows that actually work
          </p>
        </div>
        <div className={styles.benefitsGrid}>
          {benefits.map((benefit, idx) => (
            <div key={idx} className={styles.benefitCard}>
              <div className={styles.benefitIcon}>{benefit.icon}</div>
              <h3 className={styles.benefitTitle}>{benefit.title}</h3>
              <p className={styles.benefitDescription}>{benefit.description}</p>
            </div>
          ))}
        </div>
        <div className={styles.finalCta}>
          <h3>Ready to build your first AI workflow?</h3>
          <p>Join thousands of builders who are already automating with AgentMap</p>
          <Link to="/docs/intro" className="button button--primary button--lg">
            Start Building Now
          </Link>
        </div>
      </div>
    </section>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <>
      <WhatCanIBuild />
      <HowItWorks />
      <WhyAgentMap />
    </>
  );
}
