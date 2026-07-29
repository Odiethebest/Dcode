import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ThreadPane } from '@/components/workbench/ThreadPane';

function renderPane(overrides: Partial<Parameters<typeof ThreadPane>[0]> = {}) {
  const props = {
    turns: [],
    canSubmit: true,
    onSubmit: vi.fn(),
    activeCitationKey: null,
    onOpenCitation: vi.fn(),
    isStreaming: false,
    onCancel: vi.fn(),
    ...overrides,
  };
  render(<ThreadPane {...props} />);
  return props;
}

describe('ThreadPane composer', () => {
  it('sends when idle', () => {
    const { onSubmit } = renderPane();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'who calls it?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(onSubmit).toHaveBeenCalledWith('who calls it?');
  });

  it('swaps Send for Stop while streaming and refuses to submit', () => {
    // Submitting mid-stream used to silently abort the open turn. Interrupting is
    // still allowed — but only deliberately, through Stop.
    const { onSubmit, onCancel } = renderPane({ isStreaming: true });

    expect(screen.queryByRole('button', { name: 'Send' })).toBeNull();

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'a follow-up' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    expect(onCancel).toHaveBeenCalled();
  });

  it('disables the starter suggestions while streaming', () => {
    renderPane({ isStreaming: true });
    expect(screen.getByRole('button', { name: /Who calls HTTPBasicAuth/i })).toBeDisabled();
  });
});
