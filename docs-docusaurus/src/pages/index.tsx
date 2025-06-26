import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero', styles.heroBanner)}>
      <div className="container">
        <div className={styles.heroContent}>
          <div className={styles.heroText}>
            <Heading as="h1" className={styles.heroTitle}>
              {siteConfig.title}
            </Heading>
            <p className={styles.heroTagline}>{siteConfig.tagline}</p>
            <div className={styles.heroBenefits}>
              <p className={styles.benefitHighlight}>
                🚀 From CSV to Production AI Workflow in Minutes
              </p>
              <p className={styles.benefitDescription}>
                No coding required. No complex configuration. Just simple CSV files that create powerful AI workflows.
              </p>
            </div>
            <div className={styles.heroButtons}>
              <Link
                className={clsx('button button--primary button--lg', styles.ctaButton)}
                to="/docs/intro">
                Get Started in 5 Minutes
              </Link>
              <Link
                className="button button--outline button--lg"
                to="#what-can-i-build">
                See Examples
              </Link>
            </div>
          </div>
          <div className={styles.heroImage}>
            <img 
              src="/AgentMap/img/agentmap-hero.jpg" 
              alt="AgentMap Hero" 
              className={styles.heroImg}
            />
          </div>
        </div>
        <div className={styles.commandExample}>
          <div className={styles.commandBox}>
            <code>{`agentmap run --graph "WorldDomination" --state "{'input': 'Hello, world!'}"`}</code>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): JSX.Element {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`Hello from ${siteConfig.title}`}
      description="Build AI Workflows with Simple CSV Files">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
