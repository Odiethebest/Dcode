import type { ButtonHTMLAttributes } from 'react';

import { cx } from '@/lib/cx';

export type ButtonVariant = 'primary' | 'ghost';
export type ButtonSize = 'md' | 'lg';

const base =
  'inline-flex items-center justify-center gap-2 rounded-[10px] border border-transparent font-sans font-semibold leading-none transition active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60';

const variants: Record<ButtonVariant, string> = {
  // Deep-indigo brand button with the prototype's 1px seated shadow.
  primary: 'bg-brand text-white shadow-[0_1px_0_rgba(27,24,38,0.18)] hover:bg-brand-hover',
  ghost: 'bg-transparent text-ink border-line-2 hover:bg-sunk',
};

const sizes: Record<ButtonSize, string> = {
  md: 'px-[19px] py-3 text-[14.5px]',
  lg: 'rounded-[11px] px-6 py-[15px] text-[15.5px]',
};

/** The button's class string — reuse on link CTAs (`<a>`/`<Link>`) that navigate. */
export function buttonClasses(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className?: string
): string {
  return cx(base, variants[variant], sizes[size], className);
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({ variant = 'primary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return <button type={type} className={buttonClasses(variant, size, className)} {...props} />;
}
