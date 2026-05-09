import '@testing-library/jest-dom'

// ---------------------------------------------------------------------------
// Polyfills required by Radix UI primitives in jsdom
// ---------------------------------------------------------------------------

// ResizeObserver — used by @radix-ui/react-use-size (Switch, Select, etc.)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// PointerEvent — used by Radix UI dismissable layer
if (!global.PointerEvent) {
  class PointerEvent extends MouseEvent {
    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params)
    }
  }
  global.PointerEvent = PointerEvent as unknown as typeof global.PointerEvent
}

// window.matchMedia — used by some Radix UI internals
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

// scrollIntoView — not implemented in jsdom
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {}
}

// hasPointerCapture — used by Radix UI
if (!window.HTMLElement.prototype.hasPointerCapture) {
  window.HTMLElement.prototype.hasPointerCapture = () => false
}

// setPointerCapture / releasePointerCapture — used by Radix UI
if (!window.HTMLElement.prototype.setPointerCapture) {
  window.HTMLElement.prototype.setPointerCapture = () => {}
}
if (!window.HTMLElement.prototype.releasePointerCapture) {
  window.HTMLElement.prototype.releasePointerCapture = () => {}
}

// ---------------------------------------------------------------------------
// jsdom email input sanitization bypass
// jsdom sanitizes type="email" inputs and rejects invalid values (sets to '').
// We override the value setter on HTMLInputElement to allow any string value,
// which lets react-hook-form + Zod validate the raw input as entered.
// ---------------------------------------------------------------------------
const originalValueDescriptor = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype,
  'value'
)!
Object.defineProperty(window.HTMLInputElement.prototype, 'value', {
  get() {
    return originalValueDescriptor.get!.call(this)
  },
  set(value: string) {
    // For email inputs, bypass jsdom's sanitization by temporarily
    // switching to text type, setting the value, then restoring
    if (this.type === 'email') {
      const originalType = this.getAttribute('type')
      this.setAttribute('type', 'text')
      originalValueDescriptor.set!.call(this, value)
      if (originalType) {
        this.setAttribute('type', originalType)
      }
    } else {
      originalValueDescriptor.set!.call(this, value)
    }
  },
  configurable: true,
})
