from collections.abc import Iterable
from random import shuffle


# ==================== Smallest enclosing circle ====================
def _circle3(pa: complex, pb: complex, pc: complex) -> tuple[complex, float]:
    a2 = abs(pb - pc)**2
    b2 = abs(pa - pc)**2
    c2 = abs(pa - pb)**2
    wa = a2 * (b2 + c2 - a2)
    wb = b2 * (a2 + c2 - b2)
    wc = c2 * (a2 + b2 - c2)
    if wa <= 0:  # cosA <= 0
        return (pb + pc) / 2, abs(pb - pc) / 2
    if wb <= 0:
        return (pa + pc) / 2, abs(pa - pc) / 2
    if wc <= 0:
        return (pa + pb) / 2, abs(pa - pb) / 2
    center = (wa * pa + wb * pb + wc * pc) / (wa + wb + wc)
    return center, abs(center - pa)

def _circle_trivial(points: list[complex]) -> tuple[complex, float]:
    if len(points) == 0:
        return 0, float("nan")
    if len(points) == 1:
        return points[0], 0
    if len(points) == 2:
        a, b = points[0], points[1]
        return (a + b) / 2, abs(a - b) / 2
    if len(points) > 3:
        raise ValueError("Too many points")
    return _circle3(points[0], points[1], points[2])

def _welzl(points: list[complex], boundary: list[complex]) -> tuple[complex, float]:
    if not points or len(boundary) == 3:
        return _circle_trivial(boundary)
    p = points[0]
    center, radius = _welzl(points[1:], boundary)
    if abs(p - center) <= radius + 0.001:   # if radius is nan, always False
        return center, radius
    return _welzl(points, boundary + [p])

def get_covering_circle(points: Iterable[complex]) -> tuple[complex, float]:
    p = list(points)
    shuffle(p)
    return _welzl(p, [])


if __name__ == "__main__":
    from random import randint
    points = [complex(randint(0, 10000)/1000, randint(0, 10000)/1000) for _ in range(10)]
    for point in points:
        print("({0}, {1})".format(point.real, point.imag))
    center, radius = get_covering_circle(points)
    print("(x-{0})^2+(y-{1})^2={2}^2".format(center.real, center.imag, radius))

