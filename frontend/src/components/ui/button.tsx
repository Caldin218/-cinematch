import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ComponentProps } from 'react'
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
const buttonVariants=cva('inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:pointer-events-none disabled:opacity-50',{variants:{variant:{default:'bg-indigo-600 text-white hover:bg-indigo-500',outline:'border border-border bg-card hover:bg-white/5'},size:{default:'h-10 px-4',icon:'size-10'}},defaultVariants:{variant:'default',size:'default'}})
export function Button({className,variant,size,asChild=false,...props}:ComponentProps<'button'>&VariantProps<typeof buttonVariants>&{asChild?:boolean}) {const Comp=asChild?Slot:'button';return <Comp className={cn(buttonVariants({variant,size}),className)} {...props}/>}
