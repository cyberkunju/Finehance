# PWA Icons

This folder should contain app icons in the following sizes:

- icon-72.png (72x72)
- icon-96.png (96x96) 
- icon-128.png (128x128)
- icon-144.png (144x144)
- icon-152.png (152x152)
- icon-192.png (192x192)
- icon-384.png (384x384)
- icon-512.png (512x512)

## Generating Icons

You can generate these icons from a single high-resolution source image (512x512 or larger) using tools like:

1. **PWA Asset Generator**: https://www.pwabuilder.com/imageGenerator
2. **Real Favicon Generator**: https://realfavicongenerator.net/
3. **Sharp (Node.js library)**:
   ```bash
   npm install sharp
   ```
   ```js
   const sharp = require('sharp');
   const sizes = [72, 96, 128, 144, 152, 192, 384, 512];
   sizes.forEach(size => {
     sharp('source-icon.png')
       .resize(size, size)
       .toFile(`icon-${size}.png`);
   });
   ```

## Icon Guidelines

- Use a simple, recognizable design
- Ensure icons look good on both light and dark backgrounds
- For maskable icons, keep important content in the "safe zone" (center 80%)
