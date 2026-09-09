from icones import ICONES as I

def transport(son_ouvert=False):
    """Une seule ligne, que des icones. L'entree a gauche, la sortie a droite."""
    curseur = ('<div class="curseur"><div class="rail2"></div><span class="mute">M</span></div>'
               if son_ouvert else '')
    return f"""        <div class="transport">
          <span class="tb borne" title="Poser l'entree">{I['poser_in']}</span>
          <span class="sepv"></span>
          <span class="tb" title="Aller a l'entree">{I['au_in']}</span>
          <span class="tb vit" title="Lecture arriere">{I['arriere']}<span class="x">4</span></span>
          <span class="tb" title="Image precedente">{I['img_p']}</span>
          <span class="tb play" title="Lecture ou pause">{I['lecture']}</span>
          <span class="tb" title="Image suivante">{I['img_s']}</span>
          <span class="tb" title="Lecture avant">{I['avant']}</span>
          <span class="tb" title="Aller a la sortie">{I['au_out']}</span>
          <span class="sepv"></span>
          <span class="tb" title="Poser un marqueur">{I['marqueur']}</span>
          <span class="tb on" title="Lecture en boucle">{I['boucle']}</span>
          <span class="tb son" title="Volume">{I['son']}{curseur}</span>
          <span class="tb" title="Retirer les bornes">{I['retirer']}</span>
          <span class="tb borne pousse" title="Poser la sortie">{I['poser_out']}</span>
        </div>"""
