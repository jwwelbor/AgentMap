import React from 'react';
import clsx from 'clsx';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import styles from './index.module.css';

const popularLinks = [
  {
    title: '🚀 Quick Start Guide',
    href: '/docs/getting-started/quick-start',
    description: 'Build your first AI workflow in 5 minutes',
  },
  {
    title: '📚 Tutorials',
    href: '/docs/tutorials',
    description: 'Step-by-step guides for common workflows',
  },
  {
    title: '📖 Documentation',
    href: '/docs/intro',
    description: 'Complete AgentMap documentation',
  },
  {
    title: '💡 Examples',
    href: '/docs/examples',
    description: 'Real-world workflow examples',
  },
  {
    title: '🔧 API Reference',
    href: '/docs/api',
    description: 'Complete API documentation',
  },
  {
    title: '🤖 Agent Catalog',
    href: '/docs/playground',
    description: 'Browse available AI agents',
  },
];

export default function NotFound(): JSX.Element {
  const {siteConfig} = useDocusaurusContext();
  
  return (
    <Layout
      title="Page Not Found"
      description="Sorry, we couldn't find the page you're looking for."
    >
      <main className="container margin-vert--xl">
        <div className="row">
          <div className="col col--6 col--offset-3">
            <div className="text--center margin-bottom--lg">
              <h1 className="hero__title">
                🔍 Page Not Found
              </h1>
              <p className="hero__subtitle">
                Sorry, we couldn't find the page you're looking for.
              </p>
              <p>
                The page may have been moved, deleted, or you may have typed the URL incorrectly.
              </p>
            </div>

            <div className="margin-bottom--lg">
              <h2>🧭 Popular Destinations</h2>
              <div className="row">
                {popularLinks.map((link, idx) => (
                  <div key={idx} className="col col--6 margin-bottom--md">
                    <div className="card">
                      <div className="card__body">
                        <h3>{link.title}</h3>
                        <p>{link.description}</p>
                        <Link 
                          to={link.href}
                          className="button button--primary button--sm"
                        >
                          Go to Page
                        </Link>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text--center margin-bottom--lg">
              <h2>💡 What You Can Do</h2>
              <div className="row">
                <div className="col col--4">
                  <div className="card">
                    <div className="card__body text--center">
                      <h3>🏠 Go Home</h3>
                      <p>Return to the homepage and start fresh</p>
                      <Link 
                        to="/"
                        className="button button--secondary"
                      >
                        Go Home
                      </Link>
                    </div>
                  </div>
                </div>
                <div className="col col--4">
                  <div className="card">
                    <div className="card__body text--center">
                      <h3>🔍 Search Docs</h3>
                      <p>Use the search bar to find what you need</p>
                      <button 
                        className="button button--secondary"
                        onClick={() => {
                          const searchInput = document.querySelector('[placeholder*="Search"]') as HTMLInputElement;
                          if (searchInput) {
                            searchInput.focus();
                          }
                        }}
                      >
                        Open Search
                      </button>
                    </div>
                  </div>
                </div>
                <div className="col col--4">
                  <div className="card">
                    <div className="card__body text--center">
                      <h3>🐛 Report Issue</h3>
                      <p>Let us know if something is broken</p>
                      <Link 
                        to="https://github.com/jwwelbor/AgentMap/issues"
                        className="button button--secondary"
                      >
                        Report Issue
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="text--center">
              <h2>🚀 Ready to Start Building?</h2>
              <p>
                AgentMap makes it easy to build AI workflows with simple CSV files.
                Start with our quick guide and have a working bot in 5 minutes!
              </p>
              <Link
                className={clsx(
                  'button button--primary button--lg',
                  styles.getStarted,
                )}
                to="/docs/getting-started/quick-start"
              >
                Get Started Now →
              </Link>
            </div>
          </div>
        </div>
      </main>
    </Layout>
  );
}
