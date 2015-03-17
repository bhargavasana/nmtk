from django.conf import settings

import logging
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from itertools import izip

# We really just use this to get the color ramps it has available - it 
# gives us RGB colors for a wide range of things.
import matplotlib.pyplot as plt

logger=logging.getLogger(__name__)


class LegendGenerator(object):
    '''
    An NMTK Server class used to generate and manage legend objects.
    '''
    
    
    def round_to_n(self, x, n):
        '''
        Round a value to n significant digits
        '''
        flip=False
        try:
            if x < 0:
                flip=True
                x=x*-1
            if x == 0:
                return 0
            v=round(x, -int(np.floor(np.log10(x))) + (n - 1))
            if flip:
                v=v*-1
            return v
        except Exception, e:
            return x

    
    def __init__(self, color_format, min_value=None, max_value=None, 
                 reverse=False, steps=255, values_list=None,
                 min_text=None, max_text=None, units=None,
                 other_features_color=None, column_type='text'):
        '''
        There are really two ways this piece of code works - either by
        using a values list (discrete values) or a min/max value.  In the 
        latter case the assumption is that we're attempting to generate
        a color ramp of values (encompassing ranges).  In the former, the
        assumption is that we'll use discrete values split evenly across
        the specified color format/ramp
        '''
        self.units=units
        self.values_list=values_list
        self.steps=steps # The number of steps in the range.
        self.other_features_color=other_features_color

        self.include_unmatched=False
        # If the user provided min/max information then we'll need to generate
        # text under the final legend graphic showing ranges (and units), that's
        # where the code below comes in handy.  In the values list case
        # we'll generate a vertical legend, where range values are irrelevant.
        if min_value == 0:
            min_text='0'
        if max_value == 0:
            max_text='0'
        if max_text is None and max_value is not None:
            try:
                max_text='{0}'.format(self.round_to_n(max_value, 4))
            except:
                max_text='{0}'.format(max_value)
        if min_text is None and min_value is not None:
            try:
                min_text='{0}'.format(self.round_to_n(min_value, 4))
            except:
                min_text='{0}'.format(min_value)
        self.max_text=max_text
        self.min_text=min_text
        self.min_value=min_value
        self.max_value=max_value
        self.numeric=(column_type not in ('text','date',))      
        if self.numeric and min_value and max_value:
            # Increment the max value by a single step size
            # to ensure we cover all values in the range.
            ss=np.linspace(self.min_value, self.max_value, num=self.steps)[0]
#             ss=(max_value-min_value)/steps
            self.max_value=max_value+ss
        
        # Verify that the user has chosen to use one of the available color
        # ramp formats.  If they reverse it, then append an _r so that the code
        # knows to use the reverse of the ramp as appropriate.
        if color_format not in [v2 for v in self.supported_formats() for v2 in v[1]]:
            raise Exception('Unsupported color format specified')
        if reverse:
            color_format='{0}_r'.format(color_format)
        self.cmap=plt.get_cmap(color_format)
        
    def __iter__(self):
        '''
        Iterate over the values that are contained in each step (dependent on
        the steps provided to the constructor, as well as the max/min color
        provided.)  The idea here is that one could iterate over
        each of the available steps.
        
        The value iterator returns a step number, and a value indicating the 
        minimum value (greater than or equal to) that this step should match.
        
        For a min/max range it should be noted that the final color (highest one) 
        will be uniquely styled with the highest/last color value.  
        '''
        logger.debug('Initializing iterator...')
        if (self.numeric and 
            self.min_value is not None and 
            self.max_value is not None and 
            self.min_value != self.max_value):
            # This is tricky, since we need to ensure that the last max value
            # we get is included in the list of values - otherwise
            # we end up not matching the last few features!
            self.value_iterator=enumerate(np.linspace(self.min_value, self.max_value, num=self.steps))
        elif self.values_list:
            # Returns an integer (step number) and corresponding value pair,
            # in this case the min/max values are the same since we are using a 
            # values list.  Generating the color uses only the step number...
            # Here we get a list of integer values..
            self.value_iterator=izip(map(int, 
                                         np.linspace(0, self.steps, num=max(3,len(self.values_list)))), 
                                     self.values_list)
            logger.debug('Used values list...')
        else:
            self.value_iterator=iter([])
        logger.debug('Returning now that iterator is ready %s', self.value_iterator)
        return self
        
    
    def unmatched(self):
        '''
        A generic color to return based on the current ramp for "all values"
        type displays.  This returns an dictionary containing the values..
        '''
        if self.other_features_color:
            colorset_nonbytes=colorset=self.other_features_color + (255,)
#         else:
#             colorset=self.cmap(step, bytes=True)
#             colorset_nonbytes=self.cmap(step, bytes=False)
            color={'rgba': colorset[:4],
                   'rgb': colorset[:3],
                   'type': 'other',
                   'numeric': self.numeric,
                   'opacity': 100}
            return color
        else:
            return None
    
    
    def next(self):
        '''
        The "other" part of the iterator this should return a dictionary containing
        a color key (with an r,g,b tuple) and either a "value" (indicating a 
        single value) or a 'max' keys - indicating a range that 
        this color should be used for (less than match.)
        
        The opacity is a value between 0 and 1 indicating how opaque the color 
        should be (1 indicates fully opaque/100% opaque)
        '''
        # We use the value iterator to get the step and the min/max
        # values for the color.
        self._step_count=getattr(self, '_step_count',0)+1
        logger.debug('Iterating on step %s', self._step_count)
        # if the include_umatched attribute is set to true, then
        # we'll return the unmatched colors last.  Note the type of this
        # data is "other" so we can discern it from other colors.
        try:
            step, value=self.value_iterator.next()
            logger.debug('Got step and value %s %s', step, value)
        except StopIteration:
            if self.include_unmatched and self.unmatched():
                self.include_unmatched=False
                return self.unmatched()
            raise StopIteration
#         logger.debug('Next iterated value is %s, %s', step, value)   
        try:
            colorset=self.cmap(step, bytes=True)
            colorset_nonbytes=self.cmap(step, bytes=False)
            logger.debug('Color set is %s', colorset)
            color={'rgba': colorset[:4],
                   'rgb': colorset[:3],
                   'numeric': self.numeric,
                   'opacity': int(colorset_nonbytes[-1]*100)}
            if self.values_list:
                key='value'
                color['type']='values'
            else:
                key='max'
                color['type']='ramp'
            if self.numeric:
                logger.debug('Rounding %s for legend', value)
                color['legend']=self.round_to_n(value, 4)
            else:
                if not isinstance(value, (str, unicode)):
                    color['legend']=repr(value)
                else:
                    color['legend']=value
            logger.debug('Setting value')
            if not isinstance(value, (str, unicode)):
                color[key]=repr(value)
            else:
                color[key]=value
            logger.debug('Next iterated value is %s', color)
        except Exception, e:
            logger.exception('Failed to get value: %s, %s, %s',
                             value, self.values_list, color)
            raise e
        logger.debug('Returning color %s', color)
        return color
    
    @staticmethod
    def supported_formats():
        """
        Reference for colormaps included with Matplotlib.
        
        This reference example shows all colormaps included with Matplotlib. Note that
        any colormap listed here can be reversed by appending "_r" (e.g., "pink_r").
        These colormaps are divided into the following categories:
        
        Sequential:
            These colormaps are approximately monochromatic colormaps varying smoothly
            between two color tones---usually from low saturation (e.g. white) to high
            saturation (e.g. a bright blue). Sequential colormaps are ideal for
            representing most scientific data since they show a clear progression from
            low-to-high values.
        
        Diverging:
            These colormaps have a median value (usually light in color) and vary
            smoothly to two different color tones at high and low values. Diverging
            colormaps are ideal when your data has a median value that is significant
            (e.g.  0, such that positive and negative values are represented by
            different colors of the colormap).
        
        Qualitative:
            These colormaps vary rapidly in color. Qualitative colormaps are useful for
            choosing a set of discrete colors. For example::
        
                color_list = plt.cm.Set3(np.linspace(0, 1, 12))
        
            gives a list of RGB colors that are good for plotting a series of lines on
            a dark background.
        
        Miscellaneous:
            Colormaps that don't fit into the categories above.
        
        """
        return [('Sequential 1',     ['Blues', 'BuGn', 'BuPu',
                                    'GnBu', 'Greens', 'Greys', 'Oranges', 'OrRd',
                                    'PuBu', 'PuBuGn', 'PuRd', 'Purples', 'RdPu',]),
                ('Sequential 2',     ['Reds', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd',
                                    'afmhot', 'autumn', 'bone', 'cool', 'copper',
                                    'gist_heat', 'gray', 'hot', 'pink',
                                    'spring', 'summer', 'winter']),
                ('Diverging',      ['BrBG', 'bwr', 'coolwarm', 'PiYG', 'PRGn', 'PuOr',
                                    'RdBu', 'RdGy', 'RdYlBu', 'RdYlGn', 'Spectral',
                                    'seismic']),
                ('Qualitative',    ['Accent', 'Dark2', 'Paired', 'Pastel1',
                                    'Pastel2', 'Set1', 'Set2', 'Set3']),
                ('Miscellaneous',  ['gist_earth', 'terrain', 'ocean', 'gist_stern',
                                    'brg', 'CMRmap', 'cubehelix',
                                    'gnuplot', 'gnuplot2', 'gist_ncar',
                                    'nipy_spectral', 'jet', 'rainbow',
                                    'gist_rainbow', 'hsv', 'flag', 'prism'])]
        
        
        
        
    def generateSampleRamp(self, height=16, width=257):
        '''
        Generate a color ramp usign the current style.  Here we override the
        values so we can generate a sample image, then we reset them when we
        are done.  This is used by the model(s) which generate sample 
        images, as well as the legend generators, which need to generate
        an image.
        '''
        logger.debug('Generating sample ramp')
        im=Image.new('RGBA', (257, height), "black")
        logger.debug('Generating sample ramp1')

        draw=ImageDraw.Draw(im)
        start=border=1
        stop=height-border*2
        i=1
        self.old_min=self.min_value
        self.old_max=self.max_value
        self.min_value=0
        self.max_value=255
        try:
            for color in self:
                logger.debug('Generating sample ramp: %s', color)
                color="rgba({0},{1},{2},{3})".format(*color['rgba'])
                draw.line((i, start, i, stop), fill=color)
                i += 1
        finally:
            self.min_value=self.old_min
            self.max_value=self.old_max
        draw=ImageDraw.Draw(im)
        logger.debug('Generating sample ramp3')
        # if the request image size isn't the same as the ramp step
        # count, we'll resize to match - so we get an image that fills
        # the requested width.
        if width != 257:
            im=im.resize((width, height), resample=Image.NEAREST)
        return im
    
    def generateLegendGraphic(self, width=257, component_height=16,
                              ramp_text_separator=1,
                              element_separator=3,
                              graphic_text_horiz_space=5,
                              border=1,
                              other_features_text='Other features'):
        '''
        Function to use a ramp function to generate a set of values for a color ramp.
        
        Each legend graphic (whether a ramp or otherwise) is "component_height" 
        high.  In the case of a ramp, we put the text underneath the ramp and,
        include a ramp_text_separator buffer between the graphic and text (if any),
        spacing between legend components will be element_separator pixels.
        Space between a single color graphic (non ramp) and it's textual information
        will be graphic_text_horiz_space pixels.
        
        Only a single ramp can exist per image.
        
        Any features that are unmatched (in the case when a color is specified for
        other features) will be stylized using the other_features_text variable.
        '''
        font_size=12
        # iterate over the current graphic and generate an image for each
        # returned element.
        #
        # The minimum separation allowable between two pieces of legend text
        legend_text_min_separation=5
        im=None
        logger.debug('Got request to generate legend graphic')
        if ((self.min_text is not None and self.max_text is not None)
            and (self.max_value != self.min_value)):
            # Get the sample color ramp
            logger.debug('Generating color ramp legend graphic')
            im=self.generateSampleRamp(component_height, width)
            
            # Start with the font size of 12, then keep reducing until the
            # legend min/max text fits within the specified width.
            # Once we change the font size here, it'll be used everywhere for 
            # the same of consistency.
            total_text_width=width+1
            font_size +=1 # Start with a higher font size, since we start by
                          # reducing the size
            while total_text_width > width-border*2 and font_size > 0:
                # Each time recompute with the next smallest font size
                font_size -= 1
                # Compute the size of the highest text character, since this 
                # is how much the image needs to be expanded.  
                # Add in the space between the text and the ramp itself, since 
                # we need ramp_text_separator space between the two.
                font=ImageFont.truetype(settings.LEGEND_FONT,font_size)
                min_text_width, min_text_height = font.getsize('{0}'.format(self.min_text))
                max_text_width, max_text_height = font.getsize('{0}'.format(self.max_text))
                total_text_width = min_text_width + max_text_width + legend_text_min_separation
            
            # A little fudge here - some glyphys don't fit in the drawing area due to their script/style,
            # which causes some of the glyphs to go outside the bounds.  So we add 
            # three pixels to the height to compensate - which works for the "default"
            # font.  For ease of use, this is in settings also...but defaults to 3
            text_height=(max(min_text_height, max_text_height) + ramp_text_separator + 
                         getattr(settings, 'FONT_GLYPH_HORIZONTAL_COMPENSATION', 3))
            
            text_image=Image.new('RGBA', (width, text_height), "white")
            draw=ImageDraw.Draw(text_image)
            # Start writing offset from the 
            text_pos=ramp_text_separator
            draw.text((1, text_pos),
                      '{0}'.format(self.min_text),
                      fill=(0,0,0),
                      font=font)
            draw.text((width-(max_text_width+1), text_pos), 
                      '{0}'.format(self.max_text), 
                      fill=(0,0,0),
                      font=font)
            
            del draw
            final_image_height=im.size[1]+text_image.size[1]
            im3=Image.new('RGBA', (width, final_image_height))
            im3.paste(im, (0,0))
            im3.paste(text_image, (0, im.size[1]))
            im=im3
            del im3
            del text_image

            if self.units:
                units_width, units_height=font.getsize(self.units)
                # Another pixel for space, then the units text
                total_text_height = (units_height + 
                                     ramp_text_separator +
                                     getattr(settings, 'FONT_GLYPH_HORIZONTAL_COMPENSATION', 3))
                text_image=Image.new('RGBA', (width, total_text_height), "white")
                text_pos = int((width-units_width)/2)
                placement=(text_pos, ramp_text_separator)
                draw=ImageDraw.Draw(text_image)
                draw.text(placement, 
                          u'{0}'.format(self.units), 
                          fill=(0,0,0),
                          font=font)
                del draw
                final_image_height=im.size[1]+text_image.size[1]
                im3=Image.new('RGBA', (width, final_image_height))
                im3.paste(im, (0,0))
                # Paste the text where the first image ends.
                im3.paste(text_image, (0, im.size[1]))
                im=im3
        # here we build on an existing image by adding stuff for other values
        # or for a range of values.
        self.include_unmatched=True
        if not im or self.other_features_color:
            logger.debug('Generating enumerated (or other feature color) graphic')
            # In this case there wasn't a ramp, or there was a ramp and 
            # other features existed, so we need to provide legend data for that
            for color in self:
                logger.debug('Using color %s', color)
                # we already have the ramp graphic, so there's no need to 
                # include those colors (if there are any.)
                if color['type'] in ('other','values'):
                    value=color.get('value', other_features_text)
                    # Now we can use value and color['rgba'] to produce the image and text.
                    color_legend=Image.new('RGBA', (width, component_height), "white")
                    draw=ImageDraw.Draw(color_legend)
                    legend_color="rgba({0},{1},{2},{3})".format(*color['rgba'])
                    for i in range(0,component_height):
                        draw.line((i, 0, i, component_height), fill=legend_color)
                    # A little fudge here - some glyphys don't fit in the drawing area due to their script/style,
                    # which causes some of the glyphs to go outside the bounds.  So we add 
                    # three pixels to the height to compensate - which works for the "default"
                    # font.  For ease of use, this is in settings also...but defaults to 3
#                     text_height=(max(min_text_height, max_text_height) + ramp_text_separator + 
#                                  getattr(settings, 'FONT_GLYPH_HORIZONTAL_COMPENSATION', 3))
            
                    # Start writing offset from the image
                    font=ImageFont.truetype(settings.LEGEND_FONT,font_size)
                    # Offset from the left (so we don't write over the image.)
                    text_pos=component_height + legend_text_min_separation
                    text_center_offset_height=int((component_height-font_size)/2)
                    if self.units and color['type'] == 'values':
                        text='{0} ({1})'.format(value, self.units)
                    else:
                        text='{0}'.format(value,)
                    draw.text((text_pos, text_center_offset_height),
                              text,
                              fill=(0,0,0),
                              font=font)
            
                    del draw
                    if im:
                        im2=Image.new('RGBA', (width, (component_height + 
                                                       im.size[1] + 
                                                       element_separator)), "white")
                        im2.paste(im, (0,0))
                        im2.paste(color_legend, (0, im.size[1]+element_separator))
                        im=im2
                    else:
                        im=color_legend
        logger.debug('Returning graphic')
        return im