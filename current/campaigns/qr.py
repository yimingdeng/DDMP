from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def render_qr_png(data):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#123f24", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
