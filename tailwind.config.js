/** @type {import('tailwindcss').Config} */
module.exports = {
  // content: ["./templates/grappelli/**/*.{html,js}", "./templates/admin/**/*.html"],
  content: ["./templates/**/*.{html,js}"],
  theme: {
    extend: {
      fontFamily: {
        'awesome': 'FontAwesome'
      },
      maxWidth: {
        '8xl': '1440px'
      },
      typography: (theme) => ({
        DEFAULT: {
          css: {
            pre: {
              backgroundColor: theme('colors.gray.300'),
              color: theme('colors.black'),
            },
            code: {
              backgroundColor: theme('colors.gray.200'),
              '&::before': {
                content: 'none !important'
              },
              '&::after': {
                content: 'none !important'
              },
              borderRadius: '.25rem',
              padding: '0 5px',
              margin: '0 2px',
            },
            a: {
              textDecoration: 'none',
              color: theme('colors.blue.600'),
            }
          },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/line-clamp'),
    require('@tailwindcss/typography')
  ],
}
