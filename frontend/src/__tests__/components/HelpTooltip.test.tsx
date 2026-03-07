// Tests for the HelpTooltip component

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HelpTooltip, { GLOSSARY } from '../../components/HelpTooltip';

describe('HelpTooltip', () => {
  it('renders a help icon button', () => {
    render(<HelpTooltip term="SHAP" />);
    // The icon button should be present
    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('glossary contains expected terms', () => {
    const expectedTerms = [
      'Demographic Parity',
      'SHAP',
      'LIME',
      'PII',
      'k-Anonymity',
      'l-Diversity',
    ];
    for (const term of expectedTerms) {
      expect(GLOSSARY[term]).toBeDefined();
      expect(GLOSSARY[term].length).toBeGreaterThan(10);
    }
  });
});
