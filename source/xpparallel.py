import mpi4py.MPI as mpi
import numpy as np
from scipy import signal
from scipy import misc
import matplotlib.pyplot as plt
import matplotlib as mpl
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.colors import LogNorm
from matplotlib.ticker import MultipleLocator
from matplotlib.pyplot import figure
import matplotlib.patches as patches
import matplotlib as mpl
import time
mpl.rcParams['figure.dpi'] = 300
import warnings
warnings.filterwarnings("ignore")


# SELECTION DE DIMENSIONS EN PUISSANCE DE 2 | SHIFT
def shiftSelec(im1,im2,axis0,axis1):
    band2_s = np.roll(np.roll(im2,axis0,axis=0),axis1,axis=1)
    #b2 = selection(band2_s,115,1651,30,1054)
    b2 = selection(10*np.log(band2_s),115,1651,30,1054)
    b1 = selection(im1,115,1651,30,1054)
    return b1,b2

def selection(img,x0,x1,y0,y1):
    h = abs(x0 - x1)
    w = abs(y0 - y1)
    return img[x0:x0+h,y0:y0+w]

# AFFICHAGE DE 4 SUBPLOTS | ( original, tamplate, cross correlation, zoom de cross correlation )
def displayImg(original,template,corr,x,y):
    n,m = np.shape(original)
    r = 25
    fig, (ax_orig, ax_template, ax_corr, ax_corr2) = plt.subplots(1, 4,figsize=(10, 20))
    ax_orig.imshow(original)
    ax_orig.set_title('Original')

    ax_template.imshow(template)
    ax_template.set_title('Template')

    ax_corr.imshow(corr)
    nn , mm = np.shape(corr)
    nc = nn // 2
    mc = mm // 2
    rect = patches.Rectangle((nc - r,mc - r),2 * r,2 * r,linewidth=1,edgecolor='r',facecolor='none')
    ax_corr.add_patch(rect)
    ax_corr.set_title('Cross-correlation')

    rect2 = patches.Rectangle((nc - r,mc - r),2 * r,2 * r,linewidth=1,edgecolor='r',facecolor='none')
    ax_orig.add_patch(rect2)

    ax_orig.plot(x, y, 'ro')
    ax_orig.plot(n/2,n/2, 'rx')
    #ax_template.plot(x, y, 'ro')

    ax_corr2.imshow(corr[nc - r:nc + r, mc - r:mc + r])
    ax_corr2.set_title('Cross-correlation [' + str(r) + 'x' + str(r) + "]")
    ax_corr2.plot(x - nc + r, y - mc + r, 'ro')
    fig.show()

    print("(x,y) = ("+str(x)+','+str(y)+')' )

# CALCUL DE LA CORRELATION CROISEE ENTRE original ET template
def decalageBloc(original, template):
    r = 25
    orig = np.copy(original)  #prévenir pbs de pointeurs python
    temp = np.copy(template)

    orig -= original.mean()
    orig = orig/np.std(orig)
    temp -= template.mean()
    temp = temp/np.std(temp)

    corr = signal.correlate2d(orig, temp, boundary='symm', mode='same')
    n,m = np.shape(corr)
    nc = n // 2
    mc = m // 2
    y, x = np.unravel_index(np.argmax(corr[nc - r:nc + r, mc - r:mc + r]), corr[nc - r:nc + r, mc - r:mc + r].shape)  # find the match
    y = y + mc - r
    x = x + nc - r

    return orig, temp, corr, x, y

# APPLICATION CORRELATION A UNE IMAGE DECOUPEE EN BLOCS
def decoupage(b2,b1,bs,r,start,end):
    n,m = np.shape(b2)
    # VARIABLES
    tabx=[] # stockage décalage x
    taby=[] # stockage décalage y
    count = 0 # compte des blocs corrects

    for i in range(n//bs):
    #i = 0 # pour les tests
        for j in range(m//bs):
            if i * (m//bs) + j  >= start and i * (m//bs) + j < end:
                #print(i * (m//bs) + j)
                #print("rank : " + str(rank) + " | bloc #" + str(i * (m//bs) + j))
                band2Block = np.copy(b2[i*bs:(i+1)*bs,j*bs:(j+1)*bs])
                band1Block = np.copy(b1[i*bs:(i+1)*bs,j*bs:(j+1)*bs])
                templateBlock = np.copy(band1Block[5:bs-5,5:bs-5])
                orig,temp,corr,x,y = decalageBloc(band2Block,templateBlock,r)
                xm = x-bs/2
                ym = y-bs/2
                tabx.append(xm)
                taby.append(ym)
                if np.sqrt(xm**2 + ym**2) < 25 :
                    count += 1
                # tabx.append(i * (m//bs) + j)
    #print("rank : " + str(rank) + " | count : " + str(count))
    return tabx,taby,count

# APPLICATION CORRELATION CROISEE SUR DES BLOCS SUPERPOSES
def decoupageSuperpose(b2,b1,bs,r,f,start,end): # f = factor
    n,m = np.shape(b2)
    # VARIABLES
    tabx=[] # stockage décalage x
    taby=[] # stockage décalage y
    count = 0 # compte des blocs corrects

    for i in range(f * (n//bs) - (f-1)): # Parcours des blocs superposés (incertain)
        for j in range(f * (m//bs)- (f-1)):
            if i * (f * (m // bs) - (f-1)) + j  >= start and i * (f * (m // bs) - (f-1)) + j < end: # Vérification que le processus doit bien traiter ce bloc
                band2Block = np.copy(b2[int((i / f) * bs) : int((i / f) * bs + bs) , int((j / f) * bs) : int((j / f) * bs + bs)])  # Selection des blocs sur band 1 et 2
                band1Block = np.copy(b1[int((i / f) * bs) : int((i / f) * bs + bs) , int((j / f) * bs) : int((j / f) * bs + bs)])
                templateBlock = np.copy(band1Block[5:bs-5,5:bs-5])  # Selection du sous bloc
                orig,temp,corr,x,y = decalageBloc(band2Block,templateBlock) # Calcul du déplacement
                xm = x-bs/2
                ym = y-bs/2
                tabx.append(xm)
                taby.append(ym)
                if np.sqrt(xm**2 + ym**2) < 25 :
                    count += 1
    return tabx,taby,count

# AFFICHAGE DES RESULTATS DU DECOUPAGE
def visualize(b1,b2,tabx,taby,bs,axis0,axis1,r,seuil):
    n,m = np.shape(b2)
    fig,ax = plt.subplots(1,2,figsize=(10,10))
    ax[0].imshow(b2)
    ax[1].imshow(b1)
    count = 0
    for i in range(n//bs) :
        for j in range(m//bs) :
            if np.sqrt(tab[0][i * (m//bs) + j]**2 + tab[1][i * (m//bs) + j]**2) == r :
                c =  'k' # couleur noire
                l = 2 # épaisseur du trait du vecteur
            elif np.sqrt(tab[0][i * (m//bs) + j]**2 + tab[1][i * (m//bs) + j]**2)  <= seuil: # calcul de la
                c = 'm' # magenta
                l = 1
                count +=1
            else:
                c = 'r'
                l = 2
            rect = patches.Rectangle((j*bs,i*bs),bs,bs,linewidth=l,edgecolor=c,facecolor='none')
            rect2 = patches.Rectangle((j*bs,i*bs),bs,bs,linewidth=l,edgecolor=c,facecolor='none')
            arrow = patches.Arrow(j*bs + bs//2,i*bs + bs//2 ,tabx[i * (m//bs) + j],taby[i * (m//bs) + j], width=0.7,edgecolor='r',facecolor='none')
            ax[1].add_patch(arrow)
            ax[0].add_patch(rect)
            ax[1].add_patch(rect2)
    plt.tight_layout()
    plt.savefig("results/"+str(bs) + "x" + str(bs)+"_"+str(axis0) + "ax0_"+str(axis1)+"ax1_"+str(r)+"r_"+str(seuil)+"seuil_"+str(count)+ "count.png")
    print(str(count)+" blocs corrects/ "+str((n//bs)*(m//bs)))


#AFFICHAGE DES RESULTATS DU DECOUPAGE SUPERPOSE
def visualizeSuperpose(b1,b2,tab,bs,axis0,axis1,f,seuil):
    r = 25
    n,m = np.shape(b2)
    nb = (f*(n // bs) - (f-1)) * (f*(m // bs) - (f-1)) # nombr de blocs dans l'image
    fig,ax = plt.subplots(1,2,figsize=(10,10))
    ax[0].imshow(b2)
    ax[1].imshow(b1)
    count = 0
    for i in range(f * (n//bs) - (f-1)) :
        for j in range(f * (m//bs) - (f-1)) :

            if np.sqrt(tab[0][i * (f * (m//bs) - (f-1)) + j]**2 + tab[1][i *(f * (m//bs) - (f-1)) + j]**2) == r :
                c =  'k'
                l = 1
            elif np.sqrt(tab[0][i * (f * (m//bs) - (f-1)) + j]**2 + tab[1][i * (f * (m//bs) - (f-1)) + j]**2)  <= seuil:
                c = 'm'
                l = 1
                count +=1
            else:
                c = 'r'
                l = 1
            rect = patches.Rectangle( (int(j/f) * bs, int((i/f) * bs)) ,bs,bs,linewidth=l,edgecolor='k',facecolor='none')
            rect2 = patches.Rectangle( (int(j/f) * bs, int((i/f) * bs)) ,bs,bs,linewidth=l,edgecolor='k',facecolor='none')

            arrow = patches.Arrow( int((j/f) * bs + bs // 2 ) , int((i/f) *bs + bs // 2) ,tab[0][i * (f * (m//bs) - (f-1)) + j],tab[1][i * (f * (m//bs) - (f-1)) + j], width=0.7,edgecolor=c,facecolor='none')
            ax[1].add_patch(arrow)
            ax[0].add_patch(rect)
            ax[1].add_patch(rect2)

    plt.tight_layout()
    accu = (count / nb * 100)
    plt.savefig("../results/"+ str(f) + "f_" + str(bs) + "bs_" + str(axis0) + "ax1_" + str(axis1) + "ax1_" + str(seuil) + "seuil_" + str(accu) + "accu..png")
    # print(str(count)+" blocs corrects/ "+str((n//bs)*(m//bs)) + " | " + str(accu) + "% de précision")

# DONNE LE NOMBRE DE BLOCS AVEC DECALGE < SEUIL
def countCorrect(tab,seuil,nb, verbose=False):
    count = 0
    dist = []
    for i in range(nb):
        distance = np.sqrt(tab[0][i]**2 + tab[1][i]**2)
        if verbose :
            print("Décalage du block " +str(i)+ " : %.2f" % (np.sqrt(tab[0][i]**2 + tab[1][i]**2)*5) + " m.")
        if distance < seuil:  #distance inférieure à 50 px (c'est beaucoup)
            count +=1
        dist.append(distance)
    if verbose:
        print(str(count)+" corrects sur "+ str(nb) + " avec une marge de " + str(seuil * 5) +" m.")
    print("Moyenne des déplacements : " + str(np.mean(distance * 5)))
    return count, np.mean(distance*5)

# PROGRAMME PRINCIPAL
def main(axis0,axis1,bs,f,seuil):
    band1 = np.load("../data/band1.npy")
    band2 = np.load("../data/band2.npy")
    b1,b2 = shiftSelec(band1,band2,axis0,axis1)
    r = 25
    ### Distribution des blocs sur les processes
    n,m = np.shape(b2)
    if f == 1:
        nb = (n // bs) * (m // bs)
    else :
        nb = (f*(n // bs) - (f-1)) * (f*(m // bs) - (f-1)) # Nombre de blocs dans l'image

    nd = nb // size # Nombre de blocs à traiter par process
    start =  rank * nd + rank * ((rank - 1) < (nb % size)) + (rank)*((rank - 1) >= (nb % size))
    end = (rank + 1) * nd + (rank + 1) * ((rank - 1) < (nb % size)) + (rank)*((rank - 1) >= (nb % size))
    if (rank == size - 1): # Le dernier process va jusqu'au bout au cas où nb % size != 0
        end = nb
        nd = end - start

    # print("Nombre de blocs à traiter : " + str(nb))
    # print("rank : " + str(rank) + " | start : " + str(start) + " | end : " + str(end))

    tabx,taby,count = decoupageSuperpose(b2,b1,bs,r,f,start,end)

    mpi.COMM_WORLD.barrier()  # Attente de tous les processus

    c = mpi.COMM_WORLD.allreduce(sendobj = count, op = mpi.SUM)

    # Regroupement des données calculés par chaque processus
    tabx = mpi.COMM_WORLD.allgather(tabx)
    taby = mpi.COMM_WORLD.allgather(taby)

    # Correction du format renvoyé par la fonction allgather
    # Passage de 2 matrice à  1 matrice ()
    # Utile pour
    if rank == 0:
        accu = int(count / nb * 100)
        print(str(c)+" blocs corrects/ "+str(nb) + " | " + str(accu) + "% de précision")
        tab = np.zeros((2,nb))
        for k in range(size):
            for i in range(len(tabx[k])):
                tab[0][k * len(tabx[0]) + i] = tabx[k][i]
                tab[1][k * len(taby[0]) + i] = taby[k][i]

        np.save("../decoup/" + str(f) + "f_" + str(bs) + "bs" + "_"+str(axis0) + "ax1_" + str(axis1) + "ax1_" + str(seuil) + "seuil_" + str(accu) + "accu.npy", tab)  # Enregistrement des résultats pour visualisation
        #tab = np.load("../decoup/tab_superpose2.npy")  # Chargement des résultats pour visualisation
        #visualizeSuperpose(b1,b2,tab,bs,axis0,axis1,r,f,seuil) # Ligne à décommenter si visualisation directe des résultats


rank = mpi.COMM_WORLD.Get_rank() #  Numéro du process
size = mpi.COMM_WORLD.Get_size() # Nombre de process"

if rank == 0:
    t0 = time.time()

axis0 = 15 # décalage horizontal vers la gauche
axis1 = 15  # décalage vertical vers le bas
seuil = 15 # Seuil de norme pour les vecteur déplacements en px (rouge si > , magenta si <)
bs = 256 # Bloc size
f = 2 # Facteur de recouvrement
#r = 25 # norme maximale en pixel admise pour le vecteur déplacement
    #
    # ### Partie Visualisation ###
    #
    # band1 = np.load("../data/band1.npy")
    # band2 = np.load("../data/band2.npy")
    # b1,b2 = shiftSelec(band1,band2,axis0,axis1)
    # tab = np.load("../decoup/a2.npy")
    # visualizeSuperpose(b1,b2,tab,bs,axis0,axis1,r,f,seuil)
main(axis0,axis1,bs,f,seuil)
mpi.COMM_WORLD.barrier()

if rank == 0:
    t1 = time.time()
    print("Temps d'exec : " + str((t1 - t0)//60) + "min" + str((t1 - t0)%60))
