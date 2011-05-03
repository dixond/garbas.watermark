import os.path
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageEnhance import Brightness
from cStringIO import StringIO
from AccessControl import ClassSecurityInfo
from Products.Archetypes.Field import ImageField
from Products.Archetypes.Widget import ImageWidget
from Products.Archetypes.Registry import registerField

class WatermarkImageField(ImageField):
    """sends image uploaded to imagemagick for pre-treatment, especially watermarking.
    """
    _properties = ImageField._properties.copy()
    _properties.update({
        'watermark': None,
        'watermark_position': 'bottom_right',
        'watermark_margin': (0, 0),
    })

    security = ClassSecurityInfo()

    security.declarePrivate('set')
    def set(self, instance, value, **kwargs):
        if not value:
            return
        # Do we have to delete the image?
        if value=="DELETE_IMAGE":
            self.removeScales(instance, **kwargs)
            # unset main field too
            ObjectField.unset(self, instance, **kwargs)
            return

        kwargs.setdefault('mimetype', None)
        default = self.getDefault(instance)
        value, mimetype, filename = self._process_input(value, default=default,
                                                        instance=instance, **kwargs)
        # value is an OFS.Image.File based instance
        # don't store empty images
        get_size = getattr(value, 'get_size', None)
        if get_size is not None and get_size() == 0:
            return
        
        kwargs['mimetype'] = mimetype
        kwargs['filename'] = filename

        try:
            data = self.rescaleOriginal(value, **kwargs)
        except (ConflictError, KeyboardInterrupt):
            raise
        except:
            if not self.swallowResizeExceptions:
                raise
            else:
                log_exc()
                data = str(value.data)

      
        # WATERMARK - Adds a watermark to an image
        f_image = StringIO(data)
        image = Image.open(f_image)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        mark = Image.open(self.watermark)
        if self.watermark_position == 'bottom_right':
            position = (image.size[0]-mark.size[0]-self.watermark_margin[0], image.size[1]-mark.size[1]-self.watermark_margin[1])
        elif self.watermark_position == 'bottom_left':
            position = (0+self.watermark_margin[0], image.size[1]-mark.size[1]-self.watermark_margin[1])
        elif self.watermark_position == 'top_left':
            position = (0+self.watermark_margin[0], 0+self.watermark_margin[1])
        elif self.watermark_position == 'top_right':
            position = (image.size[0]-mark.size[0]-self.watermark_margin[0], 0+self.watermark_margin[1])
        else: 
            raise Exception("Unknown watermark_position specified")
        image.paste(mark, position, mark)
        textlayer = Image.new("RGBA", image.size, (0,0,0,0))
        textdraw = ImageDraw.Draw(textlayer)
        text = "Picture from: %s" % instance.Creator()
        # Ideally this would be a Plone ControlPanel configlet etc with the font as a content file upload somewhere
        font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), "GenAI102.ttf"), 16)
        textsize = textdraw.textsize(text, font=font)
        textpos = [image.size[i]-textsize[i]-self.watermark_margin[i] for i in [0,1]]
        textback = Image.new("RGBA", (textsize[0]+self.watermark_margin[0], textsize[1]+self.watermark_margin[1]), (255,255,255,255))
        textlayer.paste(textback, (textpos[0]-(self.watermark_margin[0]/2), textpos[1]-(self.watermark_margin[1]/2)), textback)
        textdraw.text(textpos, text, font=font, fill='Black')
        textlayer = self._reduce_opacity(textlayer, 0.7)
        image = Image.composite(textlayer, image, textlayer)
        f_data = StringIO()
        image.save(f_data, 'jpeg')
        data = f_data.getvalue()
        f_image.close()
        f_data.close()

        # TODO add self.ZCacheable_invalidate() later
        self.createOriginal(instance, data, **kwargs)
        self.createScales(instance, value=data)

    def _reduce_opacity(self, image, opacity):
        """Returns an image with reduced opacity."""
        assert opacity >= 0 and opacity <= 1
        alpha = image.split()[3]
        alpha = Brightness(alpha).enhance(opacity)
        image.putalpha(alpha)
        return image


registerField(WatermarkImageField,
              title='Watermark Image',
              description='A field that watermarks images.')
