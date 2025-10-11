from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

def opening_list(request):
    openings = OpeningRoot.objects.all()
    return render(request, 'repertoire/opening_list.html', {'openings': openings})


from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

def opening_detail(request, opening_id):
    opening = get_object_or_404(OpeningRoot, id=opening_id)
    main_lines = opening.linee.filter(parent__isnull=True).prefetch_related("varianti")

    return render(request, "repertoire/opening_detail.html", {
        "opening": opening,
        "main_lines": main_lines,
    })



from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

def line_detail(request, opening_id, line_num):
    opening = get_object_or_404(OpeningRoot, id=opening_id)
    line = get_object_or_404(OpeningLine, numero=line_num, root=opening)

    # Ordina tutte le linee dell’apertura
    lines = list(opening.linee.order_by('numero'))

    # Trova la posizione della linea attuale
    current_index = lines.index(line)

    # Precedente e successiva (se esistono)
    prev_line = lines[current_index - 1] if current_index > 0 else None
    next_line = lines[current_index + 1] if current_index < len(lines) - 1 else None

    return render(request, 'repertoire/line_detail.html', {
        'opening': opening,
        'line': line,
        'prev_line': prev_line,
        'next_line': next_line,
        'total_lines': len(lines),
    })



