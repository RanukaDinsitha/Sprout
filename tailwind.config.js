module.exports = {
  theme: {
    extend: {
      animation: {
        'text-blink': 'blink 0.8s infinite steps(2)',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '0' },
          '50%': { opacity: '1' },
        }
      }
    },
  },
}
