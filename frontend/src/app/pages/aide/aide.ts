import { Component } from '@angular/core';

interface Section {
  id:    string;
  title: string;
}

@Component({
  selector: 'app-aide',
  standalone: true,
  imports: [],
  templateUrl: './aide.html',
  styleUrl: './aide.scss',
})
export class AideComponent {
  sections: Section[] = [
    { id: 'comprendre',  title: 'Comprendre un capteur LoRa' },
    { id: 'confidentialite', title: 'Qui peut lire mes données ?' },
    { id: 'materiel',    title: 'Choisir son matériel' },
    { id: 'achat',       title: 'Checklist d\'achat' },
    { id: 'passerelle',  title: 'Connecter sa passerelle à TTN' },
    { id: 'ttn',         title: 'Enregistrer le capteur sur TTN' },
    { id: 'formatter',   title: 'Le payload formatter' },
    { id: 'brancher',    title: 'Brancher le capteur sur l\'app' },
    { id: 'mesures',     title: 'Grandeurs calculées' },
    { id: 'cles',        title: 'Changer les clés (commandes AT)' },
    { id: 'depannage',   title: 'Dépannage' },
    { id: 'chirpstack',  title: 'Aller plus loin : ChirpStack' },
  ];

  scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
