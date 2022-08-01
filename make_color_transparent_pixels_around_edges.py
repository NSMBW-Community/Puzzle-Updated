import random
import textwrap
import timeit
from typing import Union

StrOrInt = Union[str, int]



def color_transparent_pixels_around_edges(data: bytearray, w: int, h: int) -> None:
    """
    Find fully-transparent pixels that border non-fully-transparent
    pixels, and set their RGB channels to the average of those of their
    neighboring non-fully-transparent pixels. This solves the
    longstanding "black outlines around tile edges" bug.

    "data" should be BGRA8 bytes for an image of size "w" x "h".

    This is the unoptimized version, which is simpler and easier to
    follow. It also supports any image size.
    """
    if len(data) != w * h * 4:
        raise ValueError(f'expected {w * h * 4:#x} bytes, got {len(data):#x}')

    for y in range(h):
        for x in range(w):
            offs = (y * w + x) * 4

            if data[offs + 3] == 0:
                neighbors = []

                for x2, y2 in [
                        (x, y - 1),
                        (x + 1, y - 1),
                        (x + 1, y),
                        (x + 1, y + 1),
                        (x, y + 1),
                        (x - 1, y + 1),
                        (x - 1, y),
                        (x - 1, y - 1)]:
                    if 0 <= x2 < w and 0 <= y2 < h:
                        offs2 = ((y2 * w) + x2) * 4
                        if data[offs2 + 3]:
                            neighbors.append(data[offs2 : offs2 + 3])

                if neighbors:
                    # Calculate average R/G/B values of our neighbors,
                    # and update our own to match
                    data[offs    ] = sum(n[0] for n in neighbors) // len(neighbors)
                    data[offs + 1] = sum(n[1] for n in neighbors) // len(neighbors)
                    data[offs + 2] = sum(n[2] for n in neighbors) // len(neighbors)



def make_function(w: int, h: int) -> str:
    """
    Build source code for a "color_transparent_pixels_around_edges"
    function optimized for a specific image size.
    """
    if w < 2 or h < 2:
        raise ValueError

    stride = w * 4

    second_row = stride
    third_row = stride * 2
    second_to_last_row = stride * (h - 2)
    last_row = stride * (h - 1)
    end = stride * h

    up = -stride
    right = 4
    down = stride
    left = -4

    def hexs(s_i: StrOrInt) -> str:
        if isinstance(s_i, int):
            return hex(s_i)
        return s_i

    def get_offs(x: int, y: int) -> int:
        return y * stride + x * 4

    def add_neighbor(name: str, pixel_offset: StrOrInt, alpha_offset: StrOrInt, extra_cmd: str = '', *, indent: int = 0) -> str:
        if extra_cmd:
            extra_cmd += '\n'
        return textwrap.indent(f'''
# {name}
{extra_cmd}if data[{hexs(alpha_offset)}]:
    neighbors.append(data[{hexs(pixel_offset)} : {hexs(alpha_offset)}])
'''.strip('\n'), ' ' * indent)

    def add_relative_neighbor(name: str, offset_delta: int, *, indent: int = 0) -> str:
        if offset_delta > 0:
            extra_cmd = f'offset += {offset_delta:#x}'
        else:
            extra_cmd = f'offset -= {-offset_delta:#x}'
        return add_neighbor(name, 'offset - 3', 'offset', extra_cmd, indent=indent)

    def add_epilogue(idx_1: StrOrInt, idx_2: StrOrInt, idx_3: StrOrInt, extra_cmd: str = '', *, indent: int = 0) -> str:
        if extra_cmd:
            extra_cmd += '\n    '
        return textwrap.indent(f'''
if neighbors:
    {extra_cmd}ln = len_loc(neighbors)
    data[{hexs(idx_1)}] = sum_loc(n[0] for n in neighbors) // ln
    data[{hexs(idx_2)}] = sum_loc(n[1] for n in neighbors) // ln
    data[{hexs(idx_3)}] = sum_loc(n[2] for n in neighbors) // ln
'''.strip('\n'), ' ' * indent)

    return f'''
def color_transparent_pixels_around_edges_{w}_{h}(data: bytearray) -> None:
    """
    THIS FUNCTION IS AUTO-GENERATED SOURCE CODE!
    See make_color_transparent_pixels_around_edges.py.

    Find fully-transparent pixels that border non-fully-transparent
    pixels, and set their RGB channels to the average of those of their
    neighboring non-fully-transparent pixels. This solves the
    longstanding "black outlines around tile edges" bug.

    "data" should be BGRA8 bytes for an image of size {w}x{h}.
    """
    if len(data) != {end:#x}:
        raise ValueError(f'expected {end:#x} bytes, got {{len(data):#x}}')

    # Redefine some globals as locals for faster lookups
    sum_loc, len_loc, range_loc = sum, len, range

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top-left corner

    if not data[{get_offs(0, 0) + 3:#x}]:
        neighbors = []

{add_neighbor('(x + 1, y)', get_offs(1, 0), get_offs(1, 0) + 3, indent=8)}

{add_neighbor('(x + 1, y + 1)', get_offs(1, 1), get_offs(1, 1) + 3, indent=8)}

{add_neighbor('(x, y + 1)', get_offs(0, 1), get_offs(0, 1) + 3, indent=8)}

{add_epilogue(get_offs(0, 0), get_offs(0, 0) + 1, get_offs(0, 0) + 2, indent=8)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top-right corner

    if not data[{get_offs(w - 1, 0) + 3:#x}]:
        neighbors = []

{add_neighbor('(x, y + 1)', get_offs(w - 1, 1), get_offs(w - 1, 1) + 3, indent=8)}

{add_neighbor('(x - 1, y + 1)', get_offs(w - 2, 1), get_offs(w - 2, 1) + 3, indent=8)}

{add_neighbor('(x - 1, y)', get_offs(w - 2, 0), get_offs(w - 2, 0) + 3, indent=8)}

{add_epilogue(get_offs(w - 1, 0), get_offs(w - 1, 0) + 1, get_offs(w - 1, 0) + 2, indent=8)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom-left corner

    if not data[{get_offs(0, h - 1) + 3:#x}]:
        neighbors = []

{add_neighbor('(x, y - 1)', get_offs(0, h - 2), get_offs(0, h - 2) + 3, indent=8)}

{add_neighbor('(x + 1, y - 1)', get_offs(1, h - 2), get_offs(1, h - 2) + 3, indent=8)}

{add_neighbor('(x + 1, y)', get_offs(1, h - 1), get_offs(1, h - 1) + 3, indent=8)}

{add_epilogue(get_offs(0, h - 1), get_offs(0, h - 1) + 1, get_offs(0, h - 1) + 2, indent=8)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom-right corner

    if not data[{get_offs(w - 1, h - 1) + 3:#x}]:
        neighbors = []

{add_neighbor('(x - 1, y)', get_offs(w - 2, h - 1), get_offs(w - 2, h - 1) + 3, indent=8)}

{add_neighbor('(x - 1, y - 1)', get_offs(w - 2, h - 2), get_offs(w - 2, h - 2) + 3, indent=8)}

{add_neighbor('(x, y - 1)', get_offs(w - 1, h - 2), get_offs(w - 1, h - 2) + 3, indent=8)}

{add_epilogue(get_offs(w - 1, h - 1), get_offs(w - 1, h - 1) + 1, get_offs(w - 1, h - 1) + 2, indent=8)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top edge, except corners

    for offset in range_loc({get_offs(1, 0) + 3:#x}, {get_offs(w - 1, 0) + 3:#x}, {right:#x}):
        if not data[offset]:
            neighbors = []

{add_relative_neighbor('(x + 1, y)', right, indent=12)}

{add_relative_neighbor('(x + 1, y + 1)', down, indent=12)}

{add_relative_neighbor('(x, y + 1)', left, indent=12)}

{add_relative_neighbor('(x - 1, y + 1)', left, indent=12)}

{add_relative_neighbor('(x - 1, y)', up, indent=12)}

{add_epilogue('offset + 1', 'offset + 2', 'offset + 3', indent=12)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom edge, except corners

    for offset in range_loc({get_offs(1, h - 1) + 3:#x}, {get_offs(w - 1, h - 1) + 3:#x}, {right:#x}):
        if not data[offset]:
            neighbors = []

{add_relative_neighbor('(x - 1, y)', left, indent=12)}

{add_relative_neighbor('(x - 1, y - 1)', up, indent=12)}

{add_relative_neighbor('(x, y - 1)', right, indent=12)}

{add_relative_neighbor('(x + 1, y - 1)', right, indent=12)}

{add_relative_neighbor('(x + 1, y)', down, indent=12)}

{add_epilogue('offset - 7', 'offset - 6', 'offset - 5', indent=12)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Left edge, except corners

    for offset in range_loc({get_offs(0, 1) + 3:#x}, {get_offs(0, h - 1) + 3:#x}, {down:#x}):
        if not data[offset]:
            neighbors = []

{add_relative_neighbor('(x, y - 1)', up, indent=12)}

{add_relative_neighbor('(x + 1, y - 1)', right, indent=12)}

{add_relative_neighbor('(x + 1, y)', down, indent=12)}

{add_relative_neighbor('(x + 1, y + 1)', down, indent=12)}

{add_relative_neighbor('(x, y + 1)', left, indent=12)}

{add_epilogue('offset', 'offset + 1', 'offset + 2', f'offset -= {stride + 3:#x}', indent=12)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Right edge, except corners

    for offset in range_loc({get_offs(w - 1, 1) + 3:#x}, {get_offs(w - 1, h - 1) + 3:#x}, {down:#x}):
        if not data[offset]:
            neighbors = []

{add_relative_neighbor('(x, y + 1)', down, indent=12)}

{add_relative_neighbor('(x - 1, y + 1)', left, indent=12)}

{add_relative_neighbor('(x - 1, y)', up, indent=12)}

{add_relative_neighbor('(x - 1, y - 1)', up, indent=12)}

{add_relative_neighbor('(x, y - 1)', right, indent=12)}

{add_epilogue('offset', 'offset + 1', 'offset + 2', f'offset += {stride - 3:#x}', indent=12)}

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Main body

    for row_start_offs in range_loc({get_offs(1, 1) + 3:#x}, {get_offs(1, h - 1) + 3:#x}, {down:#x}):
        for offset in range_loc(row_start_offs, row_start_offs + {stride - 8:#x}, {right:#x}):
            if not data[offset]:  # (fully transparent pixel)
                neighbors = []

{add_relative_neighbor('(x, y - 1)', up, indent=16)}

{add_relative_neighbor('(x + 1, y - 1)', right, indent=16)}

{add_relative_neighbor('(x + 1, y)', down, indent=16)}

{add_relative_neighbor('(x + 1, y + 1)', down, indent=16)}

{add_relative_neighbor('(x, y + 1)', left, indent=16)}

{add_relative_neighbor('(x - 1, y + 1)', left, indent=16)}

{add_relative_neighbor('(x - 1, y)', up, indent=16)}

{add_relative_neighbor('(x - 1, y - 1)', up, indent=16)}

{add_epilogue('offset', 'offset + 1', 'offset + 2', f'offset += {stride + 1:#x}', indent=16)}
'''.strip('\n')


def make_test_data(w: int, h: int, *, seed = 1234) -> bytes:
    r = random.Random(seed)

    data = bytearray(w * h * 4)

    for offs in range(0, w * h * 4, 4):
        data[offs] = r.randint(0, 255)
        data[offs + 1] = r.randint(0, 255)
        data[offs + 2] = r.randint(0, 255)
        if r.randint(0, 1):
            data[offs + 3] = r.randint(1, 255)
        # else, leave it as 0

    return bytes(data)


class WeirdFakeBytearray:
    def __init__(self, fxn, iter, len=0):
        self.fxn = fxn
        self.iter = iter
        next(iter)
        self.len = len

    def run(self):
        self.fxn(self)
        try:
            self.iter.send(None)
            raise RuntimeError("iterator didn't raise StopIteration")
        except StopIteration:
            pass

    def __iter__(self):
        return self

    def __next__(self):
        raise

    def __getitem__(self, slice):
        return self.iter.send(slice)

    def __setitem__(self, slice, value):
        pass

    def __len__(self):
        return self.len


def main():

    w, h = 24, 24

    fxn_24_24_str = make_function(w, h)
    print(fxn_24_24_str)
    exec(fxn_24_24_str)

    # TODO: this test data is very non-representative of real tilesets,
    # it'd be much better to use something more realistic
    print('Preparing test data...')
    test_data = make_test_data(w, h)

    print('Running speed test for main implementation...')
    print(timeit.timeit(
        f'fxn(ba, {w}, {h})',
        setup='ba = bytearray(test_data)',
        globals={'fxn': color_transparent_pixels_around_edges, 'test_data': test_data},
        number=10) / 10)

    print('Running speed test for optimized implementation...')
    print(timeit.timeit(
        'fxn(ba)',
        setup='ba = bytearray(test_data)',
        globals={'fxn': locals()['color_transparent_pixels_around_edges_24_24'], 'test_data': test_data},
        number=10) / 10)

    # Relevant / depressing link
    # https://stackoverflow.com/q/3074784

    def weird_iterator_thing():
        expected_parents = [False] * (w * h)

        yield_next = None
        while True:
            query, yield_next = (yield yield_next), 0
            if query is None:
                break

            assert (query - 3) % 4 == 0
            y, x = divmod(query // 4, w)

            if expected_parents[y * w + x]:
                raise RuntimeError(f'Double-processed: ({x}, {y})')
            expected_parents[y * w + x] = True

            expected = set()

            for x2, y2 in [
                    (x, y - 1),
                    (x + 1, y - 1),
                    (x + 1, y),
                    (x + 1, y + 1),
                    (x, y + 1),
                    (x - 1, y + 1),
                    (x - 1, y),
                    (x - 1, y - 1)]:
                if 0 <= x2 < w and 0 <= y2 < h:
                    expected.add((x2, y2))

            while expected:
                query, yield_next = (yield yield_next), 255

                assert (query - 3) % 4 == 0
                y2, x2 = divmod(query // 4, w)

                if (x2, y2) in expected:
                    expected.remove((x2, y2))
                    query_2, yield_next = (yield yield_next), b'\0\0\0'

                    expected_2 = slice(query - 3, query, None)
                    assert query_2 == expected_2, f'function accessed the wrong RGB bytes for ({x2}, {y2}): expected {expected_2}, got {query_2}'
                else:
                    raise RuntimeError(f'function accessed a wrong neighbor pixel ({x2}, {y2}) for ({x}, {y})')

        if not all(expected_parents):
            y, x = divmod(expected_parents.index(False), w)
            raise RuntimeError(f'Missed: ({x}, {y})')

    print('Running correctness test for main implementation...')
    WeirdFakeBytearray((lambda at: color_transparent_pixels_around_edges(at, w, h)), weird_iterator_thing(), w * h * 4).run()
    print('Success!')

    print('Running correctness test for optimized implementation...')
    WeirdFakeBytearray(locals()['color_transparent_pixels_around_edges_24_24'], weird_iterator_thing(), w * h * 4).run()
    print('Success!')


if __name__ == '__main__':
    main()
